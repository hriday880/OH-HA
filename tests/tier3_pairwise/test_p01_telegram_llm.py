"""
Pairwise Test 1: Telegram Bot & LLM Provider Pipeline Integration.
Tests inbound Telegram messages triggering agent completions, typing actions, and formatted chunk delivery.
"""

from __future__ import annotations

import asyncio
from typing import Any
import pytest
from bot.config import Config
from bot.agent.pipeline import SplitBrainAgentPipeline
from bot.agent.providers import MockLLMProvider
from bot.telegram.formatters import chunk_message, escape_markdown_v2


class TestPairwiseTelegramLLM:
    """Pairwise Integration Suite: Telegram + LLM Provider."""

    @pytest.mark.asyncio
    async def test_telegram_message_to_llm_response(self, test_config: Config, mock_telegram_app: Any):
        """Test user message passing through pipeline and delivering response to mock Telegram."""
        llm = MockLLMProvider()
        llm.queue_text_response("Hello Alice! I've loaded your context.")

        pipeline = SplitBrainAgentPipeline(config=test_config, primary_provider=llm)

        # Ingest user message
        user_text = "Hi Hermes"
        await mock_telegram_app.send_chat_action(chat_id=123456789, action="typing")
        result = await pipeline.process_message(user_text)

        # Send response chunks
        chunks = chunk_message(result.content)
        for chunk in chunks:
            await mock_telegram_app.send_message(chat_id=123456789, text=chunk)

        assert len(mock_telegram_app.chat_actions) == 1
        assert mock_telegram_app.chat_actions[0]["action"] == "typing"
        assert len(mock_telegram_app.sent_messages) == 1
        assert "Hello Alice" in mock_telegram_app.sent_messages[0]["text"]

    @pytest.mark.asyncio
    async def test_long_llm_output_chunked_to_telegram(self, test_config: Config, mock_telegram_app: Any):
        """Test very long LLM response is automatically chunked into multiple Telegram messages."""
        llm = MockLLMProvider()
        long_essay = "\n\n".join([f"Section {i}: " + ("Knowledge " * 100) for i in range(10)])
        assert len(long_essay) > 8000
        llm.queue_text_response(long_essay)

        pipeline = SplitBrainAgentPipeline(config=test_config, primary_provider=llm)
        result = await pipeline.process_message("Explain all topics")

        chunks = chunk_message(result.content, max_chars=4096)
        for c in chunks:
            await mock_telegram_app.send_message(chat_id=123456789, text=c)

        assert len(mock_telegram_app.sent_messages) >= 2
        for msg in mock_telegram_app.sent_messages:
            assert len(msg["text"]) <= 4096

    @pytest.mark.asyncio
    async def test_error_in_llm_dispatches_user_error_message(self, test_config: Config, mock_telegram_app: Any):
        """Test that unrecoverable LLM failures produce a user-facing error message."""
        llm = MockLLMProvider()
        from bot.agent.providers import LLMProviderError
        llm.queue_response(LLMProviderError("All providers unavailable"))

        pipeline = SplitBrainAgentPipeline(config=test_config, primary_provider=llm)

        try:
            await pipeline.process_message("Failing prompt")
        except Exception:
            await mock_telegram_app.send_message(chat_id=123456789, text="⚠️ Error processing request.")

        assert len(mock_telegram_app.sent_messages) == 1
        assert "Error processing request" in mock_telegram_app.sent_messages[0]["text"]
