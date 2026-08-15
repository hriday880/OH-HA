"""
Acceptance Criterion 1 (AC 1) Test Suite.
Verifies: "A test script successfully mocks a Telegram message, passes it to the agent pipeline, and asserts that a response is generated."
"""

from __future__ import annotations

import asyncio
from typing import Any
import pytest
from bot.config import Config
from bot.agent.pipeline import SplitBrainAgentPipeline
from bot.agent.providers import MockLLMProvider
from bot.telegram.formatters import chunk_message


class TestAC1TelegramPipeline:
    """Acceptance Criterion 1: Mock Telegram Message -> Agent Pipeline -> Generated Response."""

    @pytest.mark.asyncio
    async def test_ac1_telegram_to_agent_response(self, test_config: Config, mock_telegram_app: Any):
        """
        [AC 1 Core Test]
        Mocks an incoming Telegram user message, passes it through the OpenHuman & Hermes
        agent pipeline, and asserts that a valid contextual response is generated and sent.
        """
        # 1. Setup deterministic LLM provider with expected companion answer
        llm = MockLLMProvider()
        expected_reply = (
            "Hello Alice! I've loaded your profile and notes. "
            "I'm ready to assist with Project Apollo or your daily goals."
        )
        llm.queue_text_response(expected_reply)

        pipeline = SplitBrainAgentPipeline(config=test_config, primary_provider=llm)

        # 2. Simulate incoming Telegram message update
        user_id = 123456789
        chat_id = 123456789
        inbound_user_message = "Good morning! Can you check in with me on my projects?"

        # 3. Emit typing indicator to mock Telegram
        await mock_telegram_app.send_chat_action(chat_id=chat_id, action="typing")

        # 4. Pass message to Agent Pipeline
        pipeline_result = await pipeline.process_message(inbound_user_message)

        # 5. Dispatch generated response to Telegram
        chunks = chunk_message(pipeline_result.content)
        for chunk in chunks:
            await mock_telegram_app.send_message(chat_id=chat_id, text=chunk)

        # 6. Assertions
        assert pipeline_result is not None
        assert pipeline_result.content == expected_reply
        assert len(mock_telegram_app.sent_messages) == 1
        assert mock_telegram_app.sent_messages[0]["chat_id"] == chat_id
        assert "Hello Alice" in mock_telegram_app.sent_messages[0]["text"]
        assert "Project Apollo" in mock_telegram_app.sent_messages[0]["text"]
        assert len(mock_telegram_app.chat_actions) == 1
        assert mock_telegram_app.chat_actions[0]["action"] == "typing"

    @pytest.mark.asyncio
    async def test_ac1_telegram_multi_turn_pipeline(self, test_config: Config, mock_telegram_app: Any):
        """Test multi-turn dialogue with continuous Telegram message processing."""
        llm = MockLLMProvider()
        llm.queue_text_response("Turn 1 reply: Yes, I am here.")
        llm.queue_text_response("Turn 2 reply: Project Apollo status is on track.")

        pipeline = SplitBrainAgentPipeline(config=test_config, primary_provider=llm)

        # Turn 1
        r1 = await pipeline.process_message("Are you online?")
        await mock_telegram_app.send_message(chat_id=123456789, text=r1.content)

        # Turn 2
        r2 = await pipeline.process_message("What about Apollo?")
        await mock_telegram_app.send_message(chat_id=123456789, text=r2.content)

        assert len(mock_telegram_app.sent_messages) == 2
        assert "Turn 1 reply" in mock_telegram_app.sent_messages[0]["text"]
        assert "Turn 2 reply" in mock_telegram_app.sent_messages[1]["text"]
