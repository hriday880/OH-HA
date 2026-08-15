"""
Tier 2 Boundary Tests: Feature 5 - Split-Brain Reflex & Intent Router.
"""

import asyncio
import unittest

from bot.config import Config
from bot.agent.pipeline import PipelineResult, ReflexIntent, SplitBrainAgentPipeline
from bot.agent.providers import LLMProviderError, LLMResponse, MockLLMProvider
from bot.agent.tools import ToolCall, ToolDefinition, ToolRegistry, ToolResult


class TestPipelineBoundary(unittest.IsolatedAsyncioTestCase):
    """Tier 2 Boundary tests for pipeline execution, tool handling, and error limits."""

    async def test_max_reasoning_steps_loop_limit(self):
        """Test pipeline terminates gracefully when max_steps is exceeded."""
        config = Config(max_reasoning_steps=3)
        mock_llm = MockLLMProvider()

        # Queue continuous tool calls exceeding 3 steps
        for i in range(5):
            mock_llm.queue_tool_call("dummy_tool", {"step": i})

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="dummy_tool", description="Dummy", parameters={"type": "object", "properties": {}}),
            lambda **kwargs: {"done": True},
        )

        pipeline = SplitBrainAgentPipeline(
            config=config,
            primary_provider=mock_llm,
            tool_registry=registry,
        )

        result = await pipeline.process_message("Infinite loop test")
        self.assertEqual(result.steps, 3)
        self.assertEqual(len(result.tools_executed), 3)
        self.assertIn("executed 3 action(s)", result.content)

    async def test_unknown_tool_call_handled_safely(self):
        """Test calling a tool that is not in registry returns structured error."""
        mock_llm = MockLLMProvider()
        mock_llm.queue_tool_call("nonexistent_tool", {"param": 1})
        mock_llm.queue_text_response("Handled unknown tool error.")

        pipeline = SplitBrainAgentPipeline(config=Config(), primary_provider=mock_llm)
        result = await pipeline.process_message("Trigger unknown tool")

        self.assertEqual(len(result.tools_executed), 1)
        self.assertTrue(result.tools_executed[0].is_error)
        self.assertIn("Unknown tool: 'nonexistent_tool'", result.tools_executed[0].error_message)
        self.assertEqual(result.content, "Handled unknown tool error.")

    async def test_tool_raising_exception_handled_safely(self):
        """Test tool execution throwing an uncaught exception is caught in ToolResult."""
        mock_llm = MockLLMProvider()
        mock_llm.queue_tool_call("buggy_tool", {})
        mock_llm.queue_text_response("Recovered from buggy tool.")

        registry = ToolRegistry()
        def crash_handler():
            raise ValueError("Corrupted data encountered!")

        registry.register(
            ToolDefinition(name="buggy_tool", description="Buggy", parameters={"type": "object", "properties": {}}),
            crash_handler,
        )

        pipeline = SplitBrainAgentPipeline(
            config=Config(),
            primary_provider=mock_llm,
            tool_registry=registry,
        )
        result = await pipeline.process_message("Run buggy tool")
        self.assertEqual(len(result.tools_executed), 1)
        self.assertTrue(result.tools_executed[0].is_error)
        self.assertIn("ValueError", result.tools_executed[0].error_message)

    async def test_async_tool_handler_execution(self):
        """Test ToolRegistry executing async coroutine handlers."""
        registry = ToolRegistry()
        async def async_search(query: str):
            await asyncio.sleep(0.01)
            return [{"title": "Note 1", "snippet": query}]

        registry.register(
            ToolDefinition(name="search_notes", description="Search", parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}),
            async_search,
        )

        res = await registry.execute(ToolCall(id="c1", name="search_notes", arguments={"query": "test query"}))
        self.assertFalse(res.is_error)
        self.assertEqual(res.result, [{"title": "Note 1", "snippet": "test query"}])

    async def test_both_providers_fail_raises_exception(self):
        """Test that exception is propagated when both primary and fallback fail."""
        primary_mock = MockLLMProvider()
        def fail_p(m, t): raise LLMProviderError("Primary down")
        primary_mock.set_custom_handler(fail_p)

        fallback_mock = MockLLMProvider()
        def fail_f(m, t): raise LLMProviderError("Fallback down")
        fallback_mock.set_custom_handler(fail_f)

        pipeline = SplitBrainAgentPipeline(
            config=Config(),
            primary_provider=primary_mock,
            fallback_provider=fallback_mock,
        )

        with self.assertRaises(LLMProviderError):
            await pipeline.process_message("Test failure")


if __name__ == "__main__":
    unittest.main()
