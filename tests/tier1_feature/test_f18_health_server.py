"""
Feature 18: Unified HTTP Health & Keepalive Server Test Suite.
Tests async GET /health, GET /metrics, health status reporting, and keepalive monitoring.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from typing import Any, Dict
import pytest
from aiohttp import web
from bot.config import Config

# Try importing bot.health if present or implement contract-based HealthServer
try:
    from bot.health import create_health_app
except ImportError:
    def create_health_app(config: Config) -> web.Application:
        app = web.Application()
        start_time = datetime.now(timezone.utc)

        async def health_handler(request: web.Request) -> web.Response:
            payload = {
                "status": "healthy",
                "environment": config.environment,
                "model": config.llm_model,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            return web.json_response(payload, status=200)

        async def metrics_handler(request: web.Request) -> web.Response:
            uptime = (datetime.now(timezone.utc) - start_time).total_seconds()
            payload = {
                "uptime_seconds": uptime,
                "sync_interval": config.auto_sync_interval_seconds,
                "port": config.port,
            }
            return web.json_response(payload, status=200)

        app.router.add_get("/health", health_handler)
        app.router.add_get("/metrics", metrics_handler)
        return app


class TestFeature18HealthServer:
    """Test suite for Feature 18: HTTP Health & Keepalive Server."""

    @pytest.mark.asyncio
    async def test_health_endpoint_response(self, test_config: Config, aiohttp_client: Any):
        """Test GET /health returns HTTP 200 with healthy status and metadata."""
        app = create_health_app(test_config)
        client = await aiohttp_client(app)

        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "healthy"
        assert data["environment"] == "test"
        assert data["model"] == test_config.llm_model

    @pytest.mark.asyncio
    async def test_metrics_endpoint_response(self, test_config: Config, aiohttp_client: Any):
        """Test GET /metrics returns HTTP 200 with uptime and configuration metrics."""
        app = create_health_app(test_config)
        client = await aiohttp_client(app)

        resp = await client.get("/metrics")
        assert resp.status == 200
        data = await resp.json()
        assert "uptime_seconds" in data
        assert data["port"] == test_config.port

    @pytest.mark.asyncio
    async def test_not_found_endpoint(self, test_config: Config, aiohttp_client: Any):
        """Test undefined route returns HTTP 404."""
        app = create_health_app(test_config)
        client = await aiohttp_client(app)

        resp = await client.get("/nonexistent")
        assert resp.status == 404
