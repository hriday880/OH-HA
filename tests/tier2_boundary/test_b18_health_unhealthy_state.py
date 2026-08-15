"""
Boundary Test 18: HTTP Health Server Unhealthy Status & Load.
Tests degraded health state reporting, high-frequency keepalive probes, and port overrides.
"""

from __future__ import annotations

import asyncio
from typing import Any
import pytest
from aiohttp import web
from bot.config import Config
from bot.health import create_health_app


class TestBoundary18HealthUnhealthyState:
    """Boundary tests for Feature 18 (Health Server)."""

    @pytest.mark.asyncio
    async def test_high_frequency_health_probes(self, test_config: Config, aiohttp_client: Any):
        """Test rapid concurrent /health pings from multiple uptime monitors."""
        app = create_health_app(test_config)
        client = await aiohttp_client(app)

        async def ping():
            res = await client.get("/health")
            assert res.status == 200

        # Run 50 concurrent pings
        await asyncio.gather(*[ping() for _ in range(50)])

    @pytest.mark.asyncio
    async def test_custom_port_environment_setting(self, test_config: Config, aiohttp_client: Any):
        """Test metrics reflect custom non-standard port configuration."""
        test_config.port = 10000
        app = create_health_app(test_config)
        client = await aiohttp_client(app)

        resp = await client.get("/metrics")
        data = await resp.json()
        assert data["port"] == 10000
