"""
Tier 2 Boundary Tests: Feature 2 - LLM Provider Adapters.
"""

import unittest

from bot.agent.providers import (
    BaseLLMProvider,
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
    MockLLMProvider,
    OpenRouterProvider,
)
from bot.agent.tools import ToolCall


class TestProvidersBoundary(unittest.IsolatedAsyncioTestCase):
    """Tier 2 Boundary tests for LLM provider adapters."""

    def test_parse_openai_compatible_response_empty_choices(self):
        """Test parsing payload when choices array is empty."""
        provider = OpenRouterProvider(api_key="sk-test")
        data = {"choices": []}
        resp = provider._parse_openai_compatible_response(data, provider_name="OpenRouter")
        self.assertIn(resp.content, (None, ""))
        self.assertEqual(resp.tool_calls, [])

    def test_parse_openai_standard_tool_calls(self):
        """Test parsing standard OpenAI JSON tool calls."""
        provider = OpenRouterProvider(api_key="sk-test")
        data = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "search_notes",
                                    "arguments": '{"query": "architecture"}',
                                },
                            }
                        ],
                    }
                }
            ],
            "model": "nousresearch/hermes-3-llama-3.1-8b",
            "usage": {"total_tokens": 120},
        }
        resp = provider._parse_openai_compatible_response(data, provider_name="OpenRouter")
        self.assertTrue(resp.has_tool_calls)
        self.assertEqual(resp.tool_calls[0].id, "call_123")
        self.assertEqual(resp.tool_calls[0].name, "search_notes")
        self.assertEqual(resp.tool_calls[0].arguments, {"query": "architecture"})
        self.assertEqual(resp.usage, {"total_tokens": 120})

    async def test_mock_provider_custom_handler(self):
        """Test MockLLMProvider with dynamic custom handler callback."""
        provider = MockLLMProvider()

        def dynamic_handler(messages, tools):
            last = messages[-1]["content"]
            return LLMResponse(content=f"Echo: {last}", provider="DynamicMock")

        provider.set_custom_handler(dynamic_handler)
        resp = await provider.chat_complete([{"role": "user", "content": "Ping"}])
        self.assertEqual(resp.content, "Echo: Ping")
        self.assertEqual(resp.provider, "DynamicMock")

    async def test_mock_provider_exhausted_queue_falls_back_to_default(self):
        """Test that MockLLMProvider returns default reply when queued responses are exhausted."""
        provider = MockLLMProvider(default_reply="Fallback reply")
        provider.queue_text_response("One-off reply")

        resp1 = await provider.chat_complete([{"role": "user", "content": "1"}])
        self.assertEqual(resp1.content, "One-off reply")

        resp2 = await provider.chat_complete([{"role": "user", "content": "2"}])
        self.assertEqual(resp2.content, "Fallback reply")

    def test_llm_response_properties(self):
        """Test LLMResponse has_tool_calls property."""
        r1 = LLMResponse(content="No tools")
        self.assertFalse(r1.has_tool_calls)

        r2 = LLMResponse(content="", tool_calls=[ToolCall(id="1", name="tool", arguments={})])
        self.assertTrue(r2.has_tool_calls)


if __name__ == "__main__":
    unittest.main()
