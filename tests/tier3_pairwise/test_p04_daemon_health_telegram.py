"""
Pairwise Test 4: Daemon Runner, HTTP Health Server & Telegram Service.
Tests concurrent execution of keepalive HTTP server and Telegram bot under single async loop.
"""

from __future__ import annotations

import asyncio
from typing import Any
import pytest
from aiohttp import web
from bot.config import Config
from bot.health import create_health_app
from bot.main import DaemonRunner
from bot.telegram.bot import TelegramBotService


class TestPairwiseDaemonHealthTelegram:
    """Pairwise Integration Suite: Daemon + Health Server + Telegram Bot."""

    @pytest.mark.asyncio
    async def test_concurrent_daemon_and_health_server(self, test_config: Config, aiohttp_client: Any):
        """Test HTTP server responds to /health while Telegram daemon is running."""
        bot_service = TelegramBotService(config=test_config)
        daemon = DaemonRunner(config=test_config, bot_service=bot_service)

        daemon_task = asyncio.create_task(daemon.run())
        await asyncio.sleep(0.02)
        assert bot_service.is_running is True

        # Test health probe
        health_app = create_health_app(test_config)
        client = await aiohttp_client(health_app)

        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "healthy"

        # Terminate daemon cleanly
        daemon.request_shutdown()
        await daemon_task
        assert bot_service.is_running is False
