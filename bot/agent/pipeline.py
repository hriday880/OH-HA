"""
Split-Brain Agent Pipeline.

Coordinates fast reflex intent triage and deep multi-step Hermes reasoning tool execution loops
with automatic fallback provider failover, memory tree grounding, and scratchpad extraction.
"""

from __future__ import annotations

import enum
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from bot.config import Config
from bot.agent.persona import MemoryTreeContext, OpenHumanPersona
from bot.agent.prompts import HermesPrompts, OpenHumanPrompts
from bot.agent.providers import (
    BaseLLMProvider,
    LLMProviderError,
    LLMResponse,
    create_llm_provider,
)
from bot.agent.tools import (
    ToolCall,
    ToolDefinition,
    ToolRegistry,
    ToolResult,
)

logger = logging.getLogger(__name__)


class ReflexIntent(str, enum.Enum):
    """Classified user message intent."""
    COMMAND = "COMMAND"
    QUICK_CHAT = "QUICK_CHAT"
    VAULT_READ = "VAULT_READ"
    VAULT_WRITE = "VAULT_WRITE"
    DEEP_REASONING = "DEEP_REASONING"


@dataclass
class PipelineResult:
    """Full execution result from the Split-Brain Agent Pipeline."""
    content: str
    thought: Optional[str] = None
    intent: ReflexIntent = ReflexIntent.DEEP_REASONING
    tools_executed: List[ToolResult] = field(default_factory=list)
    steps: int = 1
    provider_used: Optional[str] = None
    model_used: Optional[str] = None
    raw_responses: List[LLMResponse] = field(default_factory=list)


class SplitBrainAgentPipeline:
    """
    Split-Brain Agent Orchestrator combining:
    1. Reflex Layer: Fast classification & quick response shortcuts.
    2. Deep Reasoning Core: Multi-step Hermes tool calling loop with Obsidian vault context.
    3. Failover Engine: Automatic fallback to secondary provider on transient errors.
    """

    def __init__(
        self,
        config: Config,
        primary_provider: Optional[BaseLLMProvider] = None,
        fallback_provider: Optional[BaseLLMProvider] = None,
        tool_registry: Optional[ToolRegistry] = None,
        persona: Optional[OpenHumanPersona] = None,
        memory_context: Optional[MemoryTreeContext] = None,
    ) -> None:
        self.config = config
        self.primary_provider = primary_provider or create_llm_provider(
            provider_name=config.llm_provider,
            api_key=config.llm_api_key,
            model=config.llm_model,
            base_url=config.llm_base_url,
            max_retries=config.llm_max_retries,
            retry_backoff=config.llm_retry_backoff,
        )

        if fallback_provider:
            self.fallback_provider = fallback_provider
        elif config.fallback_llm_provider:
            self.fallback_provider = create_llm_provider(
                provider_name=config.fallback_llm_provider,
                api_key=config.fallback_llm_api_key,
                model=config.fallback_llm_model,
                base_url=config.fallback_llm_base_url,
                max_retries=config.llm_max_retries,
                retry_backoff=config.llm_retry_backoff,
            )
        else:
            self.fallback_provider = None

        self.tool_registry = tool_registry or ToolRegistry()
        self.persona = persona or OpenHumanPersona()
        self.memory_context = memory_context or MemoryTreeContext(vault_path=config.vault_path)
        self.max_steps = config.max_reasoning_steps

    def triage_intent(self, user_message: str) -> ReflexIntent:
        """
        Fast heuristic reflex triage to categorize message intent without unnecessary latency.
        """
        if not user_message:
            return ReflexIntent.QUICK_CHAT

        msg = user_message.strip()
        if not msg:
            return ReflexIntent.QUICK_CHAT

        if msg.startswith("/"):
            return ReflexIntent.COMMAND

        # Check if message contains only emojis or punctuation (no word chars)
        has_alpha = any(c.isalnum() for c in msg)
        if not has_alpha:
            return ReflexIntent.QUICK_CHAT

        lower = msg.lower()

        # Simple conversational greetings / acknowledgements
        quick_greetings = {
            "hi", "hello", "hello!", "hey", "hey!", "good morning", "good evening",
            "how are you", "who are you", "thanks", "thank you", "thank you!",
        }
        if lower in quick_greetings or (len(lower.split()) <= 2 and any(g in lower for g in ("hello", "hey", "hi"))):
            return ReflexIntent.QUICK_CHAT

        # Vault mutation indicators
        write_keywords = [
            "write note", "create note", "add to daily", "append to", "log task",
            "save note", "record ", "remember to ", "todo:", "write a new note",
            "write a note", "new note",
        ]
        if any(kw in lower for kw in write_keywords):
            return ReflexIntent.VAULT_WRITE

        # Vault lookup indicators
        read_keywords = [
            "read note", "read my note", "find note", "search for", "search notes",
            "look up", "what did i write", "check daily", "summarize note",
            "what are my notes", "tell me about", "view note",
        ]
        if any(kw in lower for kw in read_keywords):
            return ReflexIntent.VAULT_READ

        return ReflexIntent.DEEP_REASONING

    def classify_intent(self, user_message: str) -> ReflexIntent:
        """Alias for triage_intent."""
        return self.triage_intent(user_message)

    async def _call_provider_with_failover(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Execute chat completion with primary provider, failing over to secondary if available.
        """
        try:
            return await self.primary_provider.chat_complete(
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as primary_err:
            logger.warning(
                f"Primary LLM provider '{self.primary_provider.model}' failed: {primary_err}",
                exc_info=True,
            )
            if self.fallback_provider:
                logger.info(f"Failing over to fallback provider '{self.fallback_provider.model}'")
                try:
                    return await self.fallback_provider.chat_complete(
                        messages=messages,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                except Exception as fallback_err:
                    logger.error(
                        f"Fallback LLM provider '{self.fallback_provider.model}' also failed: {fallback_err}",
                        exc_info=True,
                    )
                    raise LLMProviderError(f"Both primary ({primary_err}) and fallback ({fallback_err}) providers failed.") from fallback_err
            raise primary_err

    def _assemble_system_prompt(self) -> str:
        """Construct full system prompt with persona, memory tree context, and tools."""
        persona_instructions = self.persona.get_instructions_text()
        memory_block = self.memory_context.build_context_block()
        tools = self.tool_registry.get_definitions()

        return OpenHumanPrompts.build_system_prompt(
            persona_instructions=persona_instructions,
            memory_context=memory_block,
            tools=tools,
            user_name=self.persona.user_name,
        )

    async def process_message(
        self,
        user_message: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        on_thought: Optional[Callable[[str], None]] = None,
    ) -> PipelineResult:
        """
        Main entrypoint: Processes an inbound user message through Reflex triage + Hermes Deep Reasoning Loop.
        """
        intent = self.triage_intent(user_message)
        logger.info(f"Processing user message with intent: {intent.value}")

        system_prompt = self._assemble_system_prompt()
        tools = self.tool_registry.get_definitions()

        # Build message context
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

        if chat_history:
            messages.extend(chat_history)

        messages.append({"role": "user", "content": user_message})

        tools_executed: List[ToolResult] = []
        raw_responses: List[LLMResponse] = []
        collected_thoughts: List[str] = []
        current_step = 0
        final_text: Optional[str] = None
        last_provider: Optional[str] = None
        last_model: Optional[str] = None

        while current_step < self.max_steps:
            current_step += 1
            logger.debug(f"Executing reasoning step {current_step}/{self.max_steps}")

            response = await self._call_provider_with_failover(
                messages=messages,
                tools=tools if tools else None,
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens,
            )

            raw_responses.append(response)
            last_provider = response.provider
            last_model = response.model

            if response.thought:
                collected_thoughts.append(response.thought)
                if on_thought:
                    try:
                        on_thought(response.thought)
                    except Exception:
                        pass

            # Check if LLM requested tool execution
            if response.has_tool_calls:
                logger.info(f"Step {current_step}: LLM invoked {len(response.tool_calls)} tool call(s)")

                # Append assistant message with tool calls
                assistant_content = response.content or ""
                # Add tool call tags if not already in content
                if not HermesPrompts.TOOL_CALL_REGEX.search(assistant_content):
                    tool_calls_xml = "\n".join(
                        f'<tool_call>\n{{"name": "{tc.name}", "arguments": {json.dumps(tc.arguments)}}}\n</tool_call>'
                        for tc in response.tool_calls
                    )
                    assistant_content = f"{assistant_content}\n{tool_calls_xml}".strip()

                messages.append({"role": "assistant", "content": assistant_content})

                # Execute all requested tool calls
                tool_responses_xml: List[str] = []
                for tool_call in response.tool_calls:
                    logger.debug(f"Executing tool '{tool_call.name}' with args: {tool_call.arguments}")
                    result = await self.tool_registry.execute(tool_call)
                    tools_executed.append(result)
                    tool_responses_xml.append(
                        HermesPrompts.format_tool_response(result.name, result.to_dict())
                    )

                # Feed tool results back to LLM as user message with <tool_response>
                combined_tool_feedback = "\n".join(tool_responses_xml)
                messages.append({"role": "user", "content": combined_tool_feedback})

                # Continue reasoning loop with updated context
                continue

            # No tool calls: final natural language answer generated
            final_text = response.content or ""
            break

        # If loop exited due to max steps without clean text
        if final_text is None:
            if tools_executed:
                success_count = sum(1 for t in tools_executed if not t.is_error)
                final_text = (
                    f"I executed {len(tools_executed)} action(s) ({success_count} succeeded). "
                    f"Please let me know if you would like me to summarize the results or perform further actions."
                )
            else:
                final_text = "I've reached the reasoning step limit. Please let me know how you'd like to proceed."

        thought_summary = "\n\n".join(collected_thoughts) if collected_thoughts else None

        return PipelineResult(
            content=final_text,
            thought=thought_summary,
            intent=intent,
            tools_executed=tools_executed,
            steps=current_step,
            provider_used=last_provider,
            model_used=last_model,
            raw_responses=raw_responses,
        )
