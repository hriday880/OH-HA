"""
Feature 5: Split-Brain Reflex & Intent Router Test Suite.
Tests intent classification, fast reflex triage, multi-step tool reasoning loops,
and secondary provider failover.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
import pytest
from bot.config import Config
from bot.agent.pipeline import PipelineResult, ReflexIntent, SplitBrainAgentPipeline
from bot.agent.providers import LLMProviderError, LLMResponse, MockLLMProvider
from bot.agent.tools import ToolCall, ToolDefinition, ToolRegistry, ToolResult


class TestFeature05SplitBrainRouter:
    """Test suite for Feature 5: Split-Brain Reflex & Intent Router."""

    def test_classify_intent_patterns(self, test_config: Config):
        """Test regex and heuristic classification into ReflexIntent enums."""
        pipeline = SplitBrainAgentPipeline(config=test_config)

        assert pipeline.classify_intent("/note Add this to daily") == ReflexIntent.COMMAND
        assert pipeline.classify_intent("/help") == ReflexIntent.COMMAND
        assert pipeline.classify_intent("Hello!") == ReflexIntent.QUICK_CHAT
        assert pipeline.classify_intent("Read my note about Apollo") == ReflexIntent.VAULT_READ
        assert pipeline.classify_intent("Write a new note for meeting") == ReflexIntent.VAULT_WRITE
        assert pipeline.classify_intent("How should we architect our distributed consensus algorithm?") == ReflexIntent.DEEP_REASONING

    @pytest.mark.asyncio
    async def test_quick_chat_pipeline_execution(self, test_config: Config):
        """Test quick chat query is handled smoothly with single-step response."""
        mock_provider = MockLLMProvider()
        mock_provider.queue_text_response("Hello Alice! How can I assist you today?")

        pipeline = SplitBrainAgentPipeline(
            config=test_config,
            primary_provider=mock_provider,
        )

        result = await pipeline.process_message("Hello!")
        assert isinstance(result, PipelineResult)
        assert "Hello Alice" in result.content
        assert result.steps == 1
        assert len(result.tools_executed) == 0

    @pytest.mark.asyncio
    async def test_multi_step_tool_reasoning_loop(self, test_config: Config):
        """Test Hermes executing a tool call, receiving the tool response, and generating final answer."""
        mock_provider = MockLLMProvider()
        # Step 1: LLM decides to call read_note
        mock_provider.queue_tool_call(
            tool_name="read_note",
            arguments={"path": "40-projects/Project_Apollo.md"},
            call_id="call_apollo_1",
        )
        # Step 2: LLM receives tool result and produces final answer
        mock_provider.queue_text_response("Project Apollo is active and focuses on autonomous cloud deployment.")

        # Register mock tool
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="read_note",
                description="Read note",
                parameters={"type": "object", "properties": {"path": {"type": "string"}}},
            ),
            lambda path: f"Content of {path}: Active Apollo project note.",
        )

        pipeline = SplitBrainAgentPipeline(
            config=test_config,
            primary_provider=mock_provider,
            tool_registry=registry,
        )

        result = await pipeline.process_message("Tell me about Project Apollo")
        assert "Project Apollo is active" in result.content
        assert result.steps == 2
        assert len(result.tools_executed) == 1
        assert result.tools_executed[0].name == "read_note"

    @pytest.mark.asyncio
    async def test_provider_failover_to_fallback(self, test_config: Config):
        """Test automatic failover to fallback provider when primary provider fails."""
        primary = MockLLMProvider()
        primary.queue_response(LLMProviderError("Primary provider 500 error"))

        fallback = MockLLMProvider()
        fallback.queue_text_response("Response delivered via fallback provider!")

        pipeline = SplitBrainAgentPipeline(
            config=test_config,
            primary_provider=primary,
            fallback_provider=fallback,
        )

        result = await pipeline.process_message("Test message for failover")
        assert "Response delivered via fallback provider!" in result.content

    @pytest.mark.asyncio
    async def test_max_reasoning_steps_limit(self, test_config: Config):
        """Test loop terminates gracefully if tool calls exceed max_reasoning_steps."""
        mock_provider = MockLLMProvider()
        # Queue continuous loop of tool calls
        for i in range(10):
            mock_provider.queue_tool_call("loop_tool", {"step": i}, call_id=f"call_{i}")

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="loop_tool", description="test", parameters={}),
            lambda **kwargs: "step result",
        )

        test_config.max_reasoning_steps = 3
        pipeline = SplitBrainAgentPipeline(
            config=test_config,
            primary_provider=mock_provider,
            tool_registry=registry,
        )

        result = await pipeline.process_message("Execute loop")
        assert result.steps <= 3
        assert len(result.tools_executed) <= 3
