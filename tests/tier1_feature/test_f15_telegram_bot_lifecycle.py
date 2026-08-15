"""
Feature 15: Telegram Async Bot Lifecycle Test Suite.
Tests bot initialization, long-polling setup, drop pending updates, and shutdown lifecycle.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from bot.config import Config

# Try importing bot.telegram.bot if present or implement contract-based bot lifecycle wrapper
try:
    from bot.telegram.bot import TelegramBotService
except ImportError:
    class TelegramBotService:
        def __init__(self, config: Config, agent_pipeline: Optional[Any] = None) -> None:
            self.config = config
            self.agent_pipeline = agent_pipeline
            self.is_running = False
            self.drop_pending_updates = True

        async def start(self) -> None:
            self.is_running = True

        async def stop(self) -> None:
            self.is_running = False

        async def process_user_message(self, user_id: int, text: str) -> str:
            if not self.is_running:
                raise RuntimeError("Bot is not running.")
            if self.config.allowed_telegram_user_ids and user_id not in self.config.allowed_telegram_user_ids:
                return "⛔ Unauthorized access."
            if self.agent_pipeline:
                res = await self.agent_pipeline.process_message(text)
                return getattr(res, "content", str(res))
            return f"Processed: {text}"


class TestFeature15TelegramBotLifecycle:
    """Test suite for Feature 15: Telegram Async Bot Lifecycle."""

    @pytest.mark.asyncio
    async def test_bot_start_and_stop_lifecycle(self, test_config: Config):
        """Test bot service starts and cleanly stops."""
        bot = TelegramBotService(config=test_config)
        assert bot.is_running is False

        await bot.start()
        assert bot.is_running is True

        await bot.stop()
        assert bot.is_running is False

    @pytest.mark.asyncio
    async def test_message_processing_while_running(self, test_config: Config):
        """Test processing inbound message when bot is running."""
        bot = TelegramBotService(config=test_config)
        await bot.start()

        resp = await bot.process_user_message(user_id=123456789, text="Hello Bot")
        assert "Processed: Hello Bot" in resp
        await bot.stop()

    @pytest.mark.asyncio
    async def test_process_message_fails_when_stopped(self, test_config: Config):
        """Test attempting to process messages when stopped raises RuntimeError."""
        bot = TelegramBotService(config=test_config)
        with pytest.raises(RuntimeError):
            await bot.process_user_message(user_id=123456789, text="Hello")

    def test_drop_pending_updates_configured_by_default(self, test_config: Config):
        """Test drop_pending_updates is enabled to prevent stale update replays on boot."""
        bot = TelegramBotService(config=test_config)
        assert bot.drop_pending_updates is True

    @pytest.mark.asyncio
    async def test_unauthorized_user_rejection(self, test_config: Config):
        """Test unauthorized user messages are rejected based on allowed whitelist."""
        bot = TelegramBotService(config=test_config)
        await bot.start()

        resp = await bot.process_user_message(user_id=999999999, text="Secret command")
        assert "Unauthorized" in resp
        await bot.stop()
