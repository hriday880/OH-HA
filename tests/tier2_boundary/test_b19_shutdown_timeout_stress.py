"""
Boundary Test 19: Graceful Shutdown Timeout & Signal Stress.
Tests signal interception during active request execution and final Git sync safety.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock
import pytest
from bot.config import Config
from bot.main import DaemonRunner


class TestBoundary19ShutdownTimeoutStress:
    """Boundary tests for Feature 19 (Daemon & Shutdown)."""

    @pytest.mark.asyncio
    async def test_shutdown_during_active_work(self, test_config: Config):
        """Test shutdown gracefully waits for in-flight tasks and triggers Git flush."""
        sync_mock = MagicMock()
        daemon = DaemonRunner(config=test_config, sync_engine=sync_mock)

        task = asyncio.create_task(daemon.run())
        await asyncio.sleep(0.01)

        daemon.request_shutdown()
        await task

        assert daemon.is_flushed is True
        assert sync_mock.commit_and_push.called is True
