"""
Boundary Test 2: LLM Provider Error & Rate Limit Handling.
Tests exhausted HTTP 429 retries, provider timeouts, HTTP 500/503 errors, and corrupted JSON payloads.
"""

from __future__ import annotations

import pytest
from bot.agent.providers import (
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
    MockLLMProvider,
    OpenRouterProvider,
)


class TestBoundary02LLMProviderErrors:
    """Boundary tests for Feature 2 (LLM Providers)."""

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises_rate_limit_error(self):
        """Test that exceeding max retries on HTTP 429 raises LLMRateLimitError."""
        provider = MockLLMProvider()
        # Queue 5 consecutive rate limit errors
        for _ in range(5):
            provider.queue_response(LLMRateLimitError("HTTP 429: Too Many Requests"))

        with pytest.raises(LLMRateLimitError):
            await provider.chat_complete(messages=[{"role": "user", "content": "test"}])

    @pytest.mark.asyncio
    async def test_timeout_error_propagation(self):
        """Test timeout exception propagation."""
        provider = MockLLMProvider()
        provider.queue_response(LLMTimeoutError("Request timed out after 60s"))

        with pytest.raises(LLMTimeoutError):
            await provider.chat_complete(messages=[{"role": "user", "content": "timeout test"}])

    @pytest.mark.asyncio
    async def test_auth_error_handling(self):
        """Test HTTP 401/403 invalid API key error handling."""
        provider = MockLLMProvider()
        provider.queue_response(LLMAuthError("HTTP 401: Invalid API Key"))

        with pytest.raises(LLMAuthError):
            await provider.chat_complete(messages=[{"role": "user", "content": "auth test"}])

    def test_corrupted_json_tool_arguments_fallback(self):
        """Test parser handles non-JSON string in tool arguments gracefully."""
        provider = OpenRouterProvider(api_key="dummy")
        data = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Running tool with broken args",
                    "tool_calls": [{
                        "id": "call_bad_json",
                        "type": "function",
                        "function": {
                            "name": "read_note",
                            "arguments": "{bad_json_not_valid_syntax: true",
                        }
                    }]
                }
            }]
        }
        res = provider._parse_openai_compatible_response(data, "openrouter")
        assert len(res.tool_calls) == 1
        assert res.tool_calls[0].name == "read_note"
        # Must not crash, should wrap raw arguments
        assert "raw_arguments" in res.tool_calls[0].arguments

    def test_empty_choices_payload_handling(self):
        """Test response with empty choices list does not crash."""
        provider = OpenRouterProvider(api_key="dummy")
        data = {"choices": []}
        res = provider._parse_openai_compatible_response(data, "openrouter")
        assert res.content is None
        assert len(res.tool_calls) == 0
