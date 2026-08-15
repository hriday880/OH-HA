"""
Tier 1 Feature Tests: Feature 2 - LLM Provider Adapters.
"""

import asyncio
import unittest

from bot.agent.providers import (
    BaseLLMProvider,
    GroqProvider,
    LLMResponse,
    MockLLMProvider,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
    TogetherProvider,
    create_llm_provider,
)
from bot.agent.tools import ToolCall, ToolDefinition, STANDARD_OBSIDIAN_TOOLS


class TestProvidersFeature(unittest.IsolatedAsyncioTestCase):
    """Tier 1 Unit tests for LLM provider adapters and MockLLMProvider."""

    async def test_provider_factory_instantiation(self):
        """Test creating various providers via create_llm_provider."""
        p_or = create_llm_provider("openrouter", api_key="sk-test")
        self.assertIsInstance(p_or, OpenRouterProvider)
        self.assertEqual(p_or.model, "nousresearch/hermes-3-llama-3.1-8b")

        p_groq = create_llm_provider("groq", api_key="gsk-test")
        self.assertIsInstance(p_groq, GroqProvider)

        p_together = create_llm_provider("together", api_key="tog-test")
        self.assertIsInstance(p_together, TogetherProvider)

        p_ollama = create_llm_provider("ollama")
        self.assertIsInstance(p_ollama, OllamaProvider)

        p_openai = create_llm_provider("openai", api_key="sk-openai")
        self.assertIsInstance(p_openai, OpenAIProvider)

        p_mock = create_llm_provider("mock")
        self.assertIsInstance(p_mock, MockLLMProvider)

    async def test_mock_provider_queue_text(self):
        """Test mock provider returning queued text responses."""
        provider = MockLLMProvider()
        provider.queue_text_response("First test response")
        provider.queue_text_response("Second test response")

        resp1 = await provider.chat_complete([{"role": "user", "content": "hello"}])
        self.assertEqual(resp1.content, "First test response")
        self.assertFalse(resp1.has_tool_calls)

        resp2 = await provider.chat_complete([{"role": "user", "content": "how are you"}])
        self.assertEqual(resp2.content, "Second test response")

    async def test_mock_provider_queue_tool_call(self):
        """Test mock provider returning queued ToolCall."""
        provider = MockLLMProvider()
        provider.queue_tool_call("read_note", {"path": "Daily/2026-08-14.md"})

        resp = await provider.chat_complete(
            messages=[{"role": "user", "content": "What's on my daily note?"}],
            tools=STANDARD_OBSIDIAN_TOOLS,
        )
        self.assertTrue(resp.has_tool_calls)
        self.assertEqual(len(resp.tool_calls), 1)
        self.assertEqual(resp.tool_calls[0].name, "read_note")
        self.assertEqual(resp.tool_calls[0].arguments, {"path": "Daily/2026-08-14.md"})

    async def test_mock_provider_hermes_xml_tool_call(self):
        """Test mock provider returning Hermes ChatML XML with thought and tool call."""
        provider = MockLLMProvider()
        provider.queue_hermes_xml_tool_call(
            tool_name="write_note",
            arguments={"path": "Daily/2026-08-14.md", "content": "- [ ] New task"},
            thought="The user requested to add a new task to daily note.",
        )

        resp = await provider.chat_complete([{"role": "user", "content": "Add task"}])
        self.assertTrue(resp.has_tool_calls)
        self.assertEqual(resp.tool_calls[0].name, "write_note")
        self.assertEqual(resp.thought, "The user requested to add a new task to daily note.")

    async def test_mock_provider_call_history(self):
        """Test mock provider tracks call history for assertions."""
        provider = MockLLMProvider(default_reply="Default reply")
        await provider.chat_complete(
            messages=[{"role": "user", "content": "Test message"}],
            temperature=0.5,
            max_tokens=256,
        )
        self.assertEqual(len(provider.call_history), 1)
        self.assertEqual(provider.call_history[0]["temperature"], 0.5)
        self.assertEqual(provider.call_history[0]["max_tokens"], 256)


if __name__ == "__main__":
    unittest.main()
