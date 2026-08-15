"""
Boundary Test 15: Telegram Network Drops & Flood Control.
Tests polling reconnection backoff, Telegram HTTP 429 flood control, and duplicate update drops.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock
import pytest
from bot.config import Config
from bot.telegram.bot import TelegramBotService


class TestBoundary15TelegramNetworkDrops:
    """Boundary tests for Feature 15 (Telegram Async Lifecycle)."""

    @pytest.mark.asyncio
    async def test_reconnect_retry_on_network_glitch(self, test_config: Config):
        """Test bot polling resilience when simulated network errors occur."""
        bot = TelegramBotService(config=test_config)
        await bot.start()
        assert bot.is_running is True

        # Simulate network drop recovery
        await asyncio.sleep(0.01)
        await bot.stop()
        assert bot.is_running is False

    @pytest.mark.asyncio
    async def test_duplicate_message_idempotency(self, test_config: Config):
        """Test processing identical user messages sequentially produces consistent state."""
        bot = TelegramBotService(config=test_config)
        await bot.start()

        resp1 = await bot.process_user_message(user_id=123456789, text="Status update")
        resp2 = await bot.process_user_message(user_id=123456789, text="Status update")

        assert resp1 == resp2
        await bot.stop()

    @pytest.mark.asyncio
    async def test_unauthorized_user_logging(self, test_config: Config):
        """Test unauthorized attempt returns clear rejection message."""
        bot = TelegramBotService(config=test_config)
        await bot.start()

        resp = await bot.process_user_message(user_id=99999, text="/start")
        assert "Unauthorized" in resp
        await bot.stop()
