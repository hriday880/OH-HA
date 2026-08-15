"""
LLM Provider Adapters.

Implements BaseLLMProvider, OpenRouterProvider, GroqProvider, TogetherProvider,
OllamaProvider, OpenAIProvider, and MockLLMProvider with structured tool calling,
exponential backoff, rate-limit retry, and failover support.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    httpx = None  # type: ignore
    _HAS_HTTPX = False

from bot.agent.prompts import HermesPrompts
from bot.agent.tools import ToolCall, ToolDefinition

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMRateLimitError(LLMProviderError):
    """Raised when provider returns HTTP 429 Too Many Requests."""
    pass


class LLMAuthError(LLMProviderError):
    """Raised when authentication fails (HTTP 401/403)."""
    pass


class LLMTimeoutError(LLMProviderError):
    """Raised when request times out."""
    pass


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw_response: Optional[Dict[str, Any]] = None
    thought: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class BaseLLMProvider(ABC):
    """Abstract async base class for all LLM providers."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "nousresearch/hermes-3-llama-3.1-8b",
        base_url: Optional[str] = None,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.timeout = timeout

    @abstractmethod
    async def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Execute chat completion with optional tool calling."""
        pass

    def _parse_openai_compatible_response(
        self,
        data: Dict[str, Any],
        provider_name: str,
    ) -> LLMResponse:
        """
        Parse OpenAI-standard response JSON into LLMResponse.
        Also parses Hermes 3 ChatML XML tool calls (<tool_call>) from content stream if present.
        """
        choices = data.get("choices", [])
        if not choices:
            return LLMResponse(content=None, raw_response=data, provider=provider_name, model=self.model)

        first_choice = choices[0]
        message = first_choice.get("message", {})
        raw_content = message.get("content")
        raw_tool_calls = message.get("tool_calls", [])

        tool_calls: List[ToolCall] = []

        # 1. Parse standard OpenAI tool_calls structure
        if raw_tool_calls:
            for idx, tc in enumerate(raw_tool_calls):
                func = tc.get("function", {})
                call_id = tc.get("id", f"call_{idx}")
                func_name = func.get("name", "")
                args_raw = func.get("arguments", {})
                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                    except Exception:
                        args = {"raw_arguments": args_raw}
                elif isinstance(args_raw, dict):
                    args = args_raw
                else:
                    args = {"raw_arguments": args_raw}
                tool_calls.append(ToolCall(id=str(call_id), name=str(func_name), arguments=args))

        # 2. Check for Hermes ChatML XML <tool_call> in content
        thought: Optional[str] = None
        clean_content: Optional[str] = raw_content

        if raw_content:
            thought, clean_content = HermesPrompts.extract_scratchpad(raw_content)
            xml_tool_calls = HermesPrompts.parse_tool_calls_from_text(raw_content)
            if xml_tool_calls and not tool_calls:
                for idx, xtc in enumerate(xml_tool_calls):
                    call_id = f"xml_call_{idx}"
                    tool_calls.append(
                        ToolCall(id=call_id, name=xtc["name"], arguments=xtc["arguments"])
                    )

        usage = data.get("usage")
        return LLMResponse(
            content=clean_content,
            tool_calls=tool_calls,
            raw_response=data,
            thought=thought,
            provider=provider_name,
            model=data.get("model", self.model),
            usage=usage,
        )

    def _sync_urllib_post(
        self,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> Tuple[int, str]:
        """Synchronous HTTP post fallback using urllib standard library."""
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                return status, body
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            return e.code, body
        except urllib.error.URLError as e:
            raise LLMTimeoutError(f"Network / connection error: {e}")

    async def _post_with_retry(
        self,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        provider_name: str,
    ) -> Dict[str, Any]:
        """Execute HTTP POST with exponential backoff and jitter for transient errors."""
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                if _HAS_HTTPX:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(url, headers=headers, json=payload)
                        status_code = response.status_code
                        body_text = response.text
                else:
                    status_code, body_text = await asyncio.to_thread(
                        self._sync_urllib_post, url, headers, payload
                    )

                if status_code == 200:
                    return json.loads(body_text)

                if status_code in (401, 403):
                    logger.error(f"Authentication failure ({status_code}) on {provider_name}: {body_text}")
                    raise LLMAuthError(f"{provider_name} auth error ({status_code}): {body_text}")

                if status_code == 429:
                    logger.warning(f"Rate limited (429) by {provider_name} on attempt {attempt+1}/{self.max_retries+1}")
                    if attempt < self.max_retries:
                        wait_time = (self.retry_backoff * (2 ** attempt)) + random.uniform(0.1, 0.5)
                        await asyncio.sleep(wait_time)
                        continue
                    raise LLMRateLimitError(f"{provider_name} rate limit exceeded: {body_text}")

                if status_code >= 500:
                    logger.warning(f"Server error ({status_code}) from {provider_name} on attempt {attempt+1}")
                    if attempt < self.max_retries:
                        wait_time = (self.retry_backoff * (2 ** attempt)) + random.uniform(0.1, 0.5)
                        await asyncio.sleep(wait_time)
                        continue
                    raise LLMProviderError(f"{provider_name} server error ({status_code}): {body_text}")

                raise LLMProviderError(f"{provider_name} HTTP {status_code}: {body_text}")

            except (LLMAuthError, LLMRateLimitError, LLMProviderError):
                raise
            except LLMTimeoutError as e:
                logger.warning(f"Timeout on {provider_name} attempt {attempt+1}: {e}")
                last_exception = e
                if attempt < self.max_retries:
                    wait_time = (self.retry_backoff * (2 ** attempt)) + random.uniform(0.1, 0.5)
                    await asyncio.sleep(wait_time)
                    continue
            except Exception as e:
                logger.warning(f"Connection error on {provider_name} attempt {attempt+1}: {e}")
                last_exception = LLMProviderError(f"Error communicating with {provider_name}: {e}")
                if attempt < self.max_retries:
                    wait_time = (self.retry_backoff * (2 ** attempt)) + random.uniform(0.1, 0.5)
                    await asyncio.sleep(wait_time)
                    continue

        if last_exception:
            raise last_exception
        raise LLMProviderError(f"Failed to get response from {provider_name} after {self.max_retries} retries")


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter API adapter (primary provider for NousResearch Hermes 3)."""

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "nousresearch/hermes-3-llama-3.1-8b"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        site_url: Optional[str] = None,
        app_name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=base_url or self.DEFAULT_BASE_URL,
            **kwargs,
        )
        self.site_url = site_url or "https://github.com/openhuman"
        self.app_name = app_name or "OpenHuman Hermes Bot"

    def _get_headers(self) -> Dict[str, str]:
        """Build OpenRouter authorization and client identity headers."""
        return {
            "Authorization": f"Bearer {self.api_key or ''}",
            "HTTP-Referer": self.site_url,
            "X-Title": self.app_name,
            "Content-Type": "application/json",
        }

    async def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = self._get_headers()

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = [tool.to_openai_schema() for tool in tools]
            payload["tool_choice"] = "auto"

        data = await self._post_with_retry(url, headers, payload, provider_name="OpenRouter")
        return self._parse_openai_compatible_response(data, provider_name="OpenRouter")


class GroqProvider(BaseLLMProvider):
    """Groq API adapter for ultra-fast Llama 3 / Hermes inference."""

    DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
    DEFAULT_MODEL = "llama-3.1-8b-instant"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=base_url or self.DEFAULT_BASE_URL,
            **kwargs,
        )

    async def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key or ''}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = [tool.to_openai_schema() for tool in tools]
            payload["tool_choice"] = "auto"

        data = await self._post_with_retry(url, headers, payload, provider_name="Groq")
        return self._parse_openai_compatible_response(data, provider_name="Groq")


class TogetherProvider(BaseLLMProvider):
    """Together AI API adapter."""

    DEFAULT_BASE_URL = "https://api.together.xyz/v1"
    DEFAULT_MODEL = "NousResearch/Hermes-3-Llama-3.1-8B"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=base_url or self.DEFAULT_BASE_URL,
            **kwargs,
        )

    async def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key or ''}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = [tool.to_openai_schema() for tool in tools]
            payload["tool_choice"] = "auto"

        data = await self._post_with_retry(url, headers, payload, provider_name="Together")
        return self._parse_openai_compatible_response(data, provider_name="Together")


class OllamaProvider(BaseLLMProvider):
    """Ollama local or remote OpenAI-compatible API adapter."""

    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "hermes3:8b"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            api_key=api_key or "ollama",
            model=model or self.DEFAULT_MODEL,
            base_url=base_url or self.DEFAULT_BASE_URL,
            **kwargs,
        )

    async def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key or 'ollama'}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = [tool.to_openai_schema() for tool in tools]

        data = await self._post_with_retry(url, headers, payload, provider_name="Ollama")
        return self._parse_openai_compatible_response(data, provider_name="Ollama")


class OpenAIProvider(BaseLLMProvider):
    """Standard OpenAI API adapter."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=base_url or self.DEFAULT_BASE_URL,
            **kwargs,
        )

    async def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key or ''}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = [tool.to_openai_schema() for tool in tools]
            payload["tool_choice"] = "auto"

        data = await self._post_with_retry(url, headers, payload, provider_name="OpenAI")
        return self._parse_openai_compatible_response(data, provider_name="OpenAI")


class MockLLMProvider(BaseLLMProvider):
    """
    In-Memory Deterministic Mock LLM Provider for unit, integration, and E2E testing.
    Can be configured with scripted responses, tool calls, dynamic reply handlers, or default replies.
    """

    def __init__(
        self,
        default_reply: str = "Hello! I am your OpenHuman AI companion.",
        responses: Optional[List[LLMResponse]] = None,
        custom_handler: Optional[Callable[[List[Dict[str, Any]], Optional[List[ToolDefinition]]], LLMResponse]] = None,
        model: str = "mock-hermes-3-8b",
        **kwargs: Any,
    ) -> None:
        super().__init__(api_key="mock-key", model=model, **kwargs)
        self.default_reply = default_reply
        self._responses: List[LLMResponse] = list(responses or [])
        self._custom_handler = custom_handler
        self.call_history: List[Dict[str, Any]] = []

    def queue_response(self, response: Any) -> None:
        """Enqueue a scripted LLMResponse, Exception to raise, or string content."""
        self._responses.append(response)

    def queue_text_response(self, text: str) -> None:
        """Enqueue a plain text LLMResponse."""
        self._responses.append(LLMResponse(content=text, provider="Mock", model=self.model))

    def queue_tool_call(self, tool_name: str, arguments: Dict[str, Any], call_id: Optional[str] = None) -> None:
        """Enqueue a tool calling response."""
        cid = call_id or f"mock_call_{len(self._responses) + 1}"
        self._responses.append(
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id=cid, name=tool_name, arguments=arguments)],
                provider="Mock",
                model=self.model,
            )
        )

    def queue_hermes_xml_tool_call(self, tool_name: str, arguments: Dict[str, Any], thought: Optional[str] = None) -> None:
        """Enqueue a response formatted as raw Hermes 3 ChatML with <tool_call> and <thought>."""
        thought_block = f"<thought>{thought}</thought>\n" if thought else ""
        tool_block = f'<tool_call>\n{{"name": "{tool_name}", "arguments": {json.dumps(arguments)}}}\n</tool_call>'
        full_content = f"{thought_block}{tool_block}"
        self._responses.append(
            LLMResponse(
                content=full_content,
                tool_calls=[ToolCall(id=f"xml_call_{len(self._responses)}", name=tool_name, arguments=arguments)],
                thought=thought,
                provider="Mock",
                model=self.model,
            )
        )

    def set_custom_handler(
        self,
        handler: Callable[[List[Dict[str, Any]], Optional[List[ToolDefinition]]], LLMResponse],
    ) -> None:
        self._custom_handler = handler

    async def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        self.call_history.append({
            "messages": messages,
            "tools": tools,
            "temperature": temperature,
            "max_tokens": max_tokens,
        })

        if self._custom_handler is not None:
            return self._custom_handler(messages, tools)

        if self._responses:
            item = self._responses.pop(0)
            if isinstance(item, Exception):
                raise item
            if isinstance(item, str):
                return LLMResponse(content=item, provider="Mock", model=self.model)
            return item

        # Smart default: If last user message contains specific keywords, simulate relevant action
        last_msg = messages[-1].get("content", "") if messages else ""
        if isinstance(last_msg, str) and "<tool_response>" in last_msg:
            # Responding to a tool execution
            return LLMResponse(
                content=f"Successfully processed your request with the vault.",
                provider="Mock",
                model=self.model,
            )

        return LLMResponse(
            content=self.default_reply,
            provider="Mock",
            model=self.model,
        )


def create_llm_provider(
    provider_name: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    max_retries: int = 3,
    retry_backoff: float = 1.0,
) -> BaseLLMProvider:
    """
    Factory function to instantiate LLMProvider by name.
    """
    norm_name = (provider_name or "openrouter").lower().strip()

    if norm_name == "openrouter":
        return OpenRouterProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )
    elif norm_name == "groq":
        return GroqProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )
    elif norm_name == "together":
        return TogetherProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )
    elif norm_name in ("ollama", "local"):
        return OllamaProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )
    elif norm_name == "openai":
        return OpenAIProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )
    elif norm_name == "mock":
        return MockLLMProvider(model=model or "mock-hermes-3-8b")
    else:
        logger.warning(f"Unknown provider '{provider_name}', defaulting to OpenRouterProvider")
        return OpenRouterProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )
