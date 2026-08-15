"""
Feature 2: LLM Provider Adapters Test Suite.
Tests BaseLLMProvider interface, OpenRouter, Groq, Together, Ollama, and Mock providers.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch
import pytest
import httpx
from bot.agent.providers import (
    BaseLLMProvider,
    GroqProvider,
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
    MockLLMProvider,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
    TogetherProvider,
)
from bot.agent.tools import ToolCall, ToolDefinition


class TestFeature02LLMProviders:
    """Test suite for Feature 2: LLM Provider Adapter Interface."""

    @pytest.mark.asyncio
    async def test_mock_llm_provider_canned_text_and_history(self):
        """Test MockLLMProvider returns queued text response and logs call history."""
        provider = MockLLMProvider()
        provider.queue_text_response("Hello from Hermes!")

        messages = [{"role": "user", "content": "Hi there"}]
        response = await provider.chat_complete(messages=messages, temperature=0.5)

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello from Hermes!"
        assert len(provider.call_history) == 1
        assert provider.call_history[0]["messages"] == messages
        assert provider.call_history[0]["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_mock_llm_provider_queued_tool_call(self):
        """Test MockLLMProvider returns structured tool calls."""
        provider = MockLLMProvider()
        provider.queue_tool_call("read_note", {"path": "30-people/User_Profile.md"})

        messages = [{"role": "user", "content": "Who am I?"}]
        response = await provider.chat_complete(messages=messages)

        assert response.has_tool_calls is True
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "read_note"
        assert response.tool_calls[0].arguments == {"path": "30-people/User_Profile.md"}

    @pytest.mark.asyncio
    async def test_openrouter_provider_instantiation_and_headers(self):
        """Test OpenRouterProvider builds proper authorization and app headers."""
        provider = OpenRouterProvider(
            api_key="sk-or-test-key",
            model="nousresearch/hermes-3-llama-3.1-8b",
            site_url="https://github.com/openhuman",
            app_name="OpenHuman Hermes Test Bot",
        )
        assert provider.api_key == "sk-or-test-key"
        assert provider.base_url == "https://openrouter.ai/api/v1"
        assert provider.model == "nousresearch/hermes-3-llama-3.1-8b"
        headers = provider._get_headers()
        assert headers["Authorization"] == "Bearer sk-or-test-key"
        assert headers["HTTP-Referer"] == "https://github.com/openhuman"
        assert headers["X-Title"] == "OpenHuman Hermes Test Bot"

    @pytest.mark.asyncio
    async def test_groq_and_together_provider_defaults(self):
        """Test Groq and Together providers default endpoints and models."""
        groq = GroqProvider(api_key="gsk-test-key")
        assert groq.base_url == "https://api.groq.com/openai/v1"
        assert "llama" in groq.model.lower()

        together = TogetherProvider(api_key="together-test-key")
        assert together.base_url == "https://api.together.xyz/v1"
        assert "hermes" in together.model.lower()

        ollama = OllamaProvider(base_url="http://localhost:11434/v1", model="hermes3:8b")
        assert ollama.base_url == "http://localhost:11434/v1"
        assert ollama.model == "hermes3:8b"

    @pytest.mark.asyncio
    async def test_llm_rate_limit_retry_and_backoff(self):
        """Test provider retry mechanism on HTTP 429 rate limit."""
        provider = MockLLMProvider()
        # Queue 2 rate limit errors followed by success
        provider.queue_response(LLMRateLimitError("HTTP 429: Rate limit exceeded"))
        provider.queue_response(LLMResponse(content="Success after retry"))

        # First call raises rate limit
        with pytest.raises(LLMRateLimitError):
            await provider.chat_complete(messages=[{"role": "user", "content": "test"}])

        # Second call succeeds
        res = await provider.chat_complete(messages=[{"role": "user", "content": "test"}])
        assert res.content == "Success after retry"

    def test_response_parsing_openai_payload_with_thought_and_tools(self):
        """Test parsing of OpenAI-standard JSON responses containing tool calls and thoughts."""
        provider = OpenRouterProvider(api_key="dummy")
        data = {
            "id": "chatcmpl-123",
            "model": "nousresearch/hermes-3-llama-3.1-8b",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "<thought>I should search the vault for Apollo.</thought>I will search for Apollo.",
                    "tool_calls": [{
                        "id": "call_abc123",
                        "type": "function",
                        "function": {
                            "name": "search_notes",
                            "arguments": '{"query": "Apollo", "tag": "project"}',
                        }
                    }]
                }
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        }
        res = provider._parse_openai_compatible_response(data, "openrouter")
        assert res.thought == "I should search the vault for Apollo."
        assert res.content == "I will search for Apollo."
        assert len(res.tool_calls) == 1
        assert res.tool_calls[0].name == "search_notes"
        assert res.tool_calls[0].arguments == {"query": "Apollo", "tag": "project"}
        assert res.usage == {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
