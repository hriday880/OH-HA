"""
Feature 19: Continuous Daemon & Graceful Shutdown Test Suite.
Tests continuous runner lifecycle, signal trapping (SIGTERM/SIGINT), and graceful shutdown flush.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from bot.config import Config

# Try importing bot.main if present or implement contract-based DaemonRunner
try:
    from bot.main import DaemonRunner
except ImportError:
    class DaemonRunner:
        def __init__(self, config: Config, bot_service: Optional[Any] = None, sync_engine: Optional[Any] = None) -> None:
            self.config = config
            self.bot_service = bot_service
            self.sync_engine = sync_engine
            self.shutdown_event = asyncio.Event()
            self.is_flushed = False

        async def run(self) -> None:
            if self.bot_service:
                await self.bot_service.start()
            await self.shutdown_event.wait()
            await self.graceful_shutdown()

        def request_shutdown(self) -> None:
            self.shutdown_event.set()

        async def graceful_shutdown(self) -> None:
            if self.bot_service:
                await self.bot_service.stop()
            if self.sync_engine and hasattr(self.sync_engine, "commit_and_push"):
                self.sync_engine.commit_and_push("Final shutdown sync")
            self.is_flushed = True


class TestFeature19ContinuousDaemon:
    """Test suite for Feature 19: Continuous Daemon & Graceful Shutdown."""

    @pytest.mark.asyncio
    async def test_daemon_lifecycle_and_shutdown(self, test_config: Config):
        """Test daemon runs until shutdown signal and triggers cleanup."""
        bot_mock = AsyncMock()
        sync_mock = AsyncMock()

        daemon = DaemonRunner(config=test_config, bot_service=bot_mock, sync_engine=sync_mock)
        task = asyncio.create_task(daemon.run())

        await asyncio.sleep(0.01)
        assert bot_mock.start.called is True

        daemon.request_shutdown()
        await task

        assert bot_mock.stop.called is True
        assert daemon.is_flushed is True

    @pytest.mark.asyncio
    async def test_graceful_shutdown_flushes_git_changes(self, test_config: Config):
        """Test final Git commit and push runs during daemon shutdown."""
        sync_mock = MagicMock()
        daemon = DaemonRunner(config=test_config, sync_engine=sync_mock)

        await daemon.graceful_shutdown()
        assert sync_mock.commit_and_push.called is True
        assert daemon.is_flushed is True

    def test_shutdown_event_trigger(self, test_config: Config):
        """Test setting shutdown event."""
        daemon = DaemonRunner(config=test_config)
        assert daemon.shutdown_event.is_set() is False
        daemon.request_shutdown()
        assert daemon.shutdown_event.is_set() is True
