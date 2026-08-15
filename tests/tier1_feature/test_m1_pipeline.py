"""
Tier 1 Feature Tests: Feature 5 - Split-Brain Reflex & Intent Router.
"""

import asyncio
import unittest
from pathlib import Path

from bot.config import Config
from bot.agent.pipeline import PipelineResult, ReflexIntent, SplitBrainAgentPipeline
from bot.agent.providers import LLMProviderError, LLMResponse, MockLLMProvider
from bot.agent.tools import ToolCall, ToolDefinition, ToolRegistry, ToolResult
from tests.conftest import create_temp_vault, cleanup_temp_vault


class TestPipelineFeature(unittest.IsolatedAsyncioTestCase):
    """Tier 1 Unit tests for Split-Brain reflex triage and reasoning tool loop."""

    def setUp(self):
        self.vault_path = create_temp_vault()
        self.config = Config(vault_path=self.vault_path, max_reasoning_steps=5)

    def tearDown(self):
        cleanup_temp_vault(self.vault_path)

    def test_reflex_triage_intents(self):
        """Test fast heuristic classification for various user inputs."""
        pipeline = SplitBrainAgentPipeline(config=self.config)

        self.assertEqual(pipeline.triage_intent("/start"), ReflexIntent.COMMAND)
        self.assertEqual(pipeline.triage_intent("/note meeting summary"), ReflexIntent.COMMAND)
        self.assertEqual(pipeline.triage_intent("hello"), ReflexIntent.QUICK_CHAT)
        self.assertEqual(pipeline.triage_intent("write note to Projects/Demo.md"), ReflexIntent.VAULT_WRITE)
        self.assertEqual(pipeline.triage_intent("search for active tasks in vault"), ReflexIntent.VAULT_READ)
        self.assertEqual(pipeline.triage_intent("Can you help me design an agent architecture?"), ReflexIntent.DEEP_REASONING)

    async def test_single_turn_conversation_pipeline(self):
        """Test single-turn conversation without tool calling."""
        mock_llm = MockLLMProvider(default_reply="I am doing great, thank you!")
        pipeline = SplitBrainAgentPipeline(config=self.config, primary_provider=mock_llm)

        result = await pipeline.process_message("How are you?")
        self.assertIsInstance(result, PipelineResult)
        self.assertEqual(result.content, "I am doing great, thank you!")
        self.assertEqual(result.steps, 1)
        self.assertEqual(len(result.tools_executed), 0)

    async def test_multi_step_tool_execution_loop(self):
        """Test multi-turn Hermes tool execution reasoning loop."""
        mock_llm = MockLLMProvider()
        # Step 1: LLM outputs tool call
        mock_llm.queue_tool_call(
            tool_name="read_note",
            arguments={"path": "Daily/2026-08-14.md"},
            call_id="call_read_1",
        )
        # Step 2: LLM outputs final response summarizing the tool result
        mock_llm.queue_text_response("In your daily note, you completed refactoring LLM provider adapters.")

        # Register mock read_note tool
        registry = ToolRegistry()
        def mock_read_note(path: str):
            return {"content": "- [x] Refactored LLM provider adapters\n- [ ] Split-brain reasoning loop"}

        registry.register(
            ToolDefinition(name="read_note", description="Read note", parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}),
            mock_read_note,
        )

        pipeline = SplitBrainAgentPipeline(
            config=self.config,
            primary_provider=mock_llm,
            tool_registry=registry,
        )

        result = await pipeline.process_message("What did I work on today?")
        self.assertEqual(result.steps, 2)
        self.assertEqual(len(result.tools_executed), 1)
        self.assertFalse(result.tools_executed[0].is_error)
        self.assertEqual(result.tools_executed[0].name, "read_note")
        self.assertIn("refactoring LLM provider adapters", result.content)

    async def test_provider_failover_mechanism(self):
        """Test automatic failover to secondary provider when primary fails."""
        primary_mock = MockLLMProvider()
        def failing_handler(messages, tools):
            raise LLMProviderError("Primary provider connection failed")
        primary_mock.set_custom_handler(failing_handler)

        fallback_mock = MockLLMProvider(default_reply="Response from fallback provider")

        pipeline = SplitBrainAgentPipeline(
            config=self.config,
            primary_provider=primary_mock,
            fallback_provider=fallback_mock,
        )

        result = await pipeline.process_message("Hello from test")
        self.assertEqual(result.content, "Response from fallback provider")


if __name__ == "__main__":
    unittest.main()
