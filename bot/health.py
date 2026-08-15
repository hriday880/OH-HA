"""
Unified Async HTTP Health & Keepalive Server.

Provides a lightweight aiohttp HTTP server running on $PORT to satisfy cloud container
keepalive monitors (e.g. Render, Fly.io, UptimeRobot) with /health and /metrics endpoints.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from aiohttp import web

from bot.config import Config

logger = logging.getLogger(__name__)


def create_health_app(
    config: Config,
    bot_service: Optional[Any] = None,
    sync_engine: Optional[Any] = None,
) -> web.Application:
    """
    Create and configure the aiohttp Application for health and metric monitoring.

    Args:
        config: Application configuration settings.
        bot_service: Optional TelegramBotService instance to inspect.
        sync_engine: Optional GitSyncEngine instance to inspect.

    Returns:
        Configured aiohttp.web.Application.
    """
    app = web.Application()
    start_time = datetime.now(timezone.utc)

    async def health_handler(request: web.Request) -> web.Response:
        """
        GET /health
        Returns 200 OK with system operational status and metadata.
        """
        now = datetime.now(timezone.utc)
        payload: Dict[str, Any] = {
            "status": "healthy",
            "environment": config.environment,
            "model": config.llm_model,
            "timestamp": now.isoformat(),
        }

        if bot_service is not None:
            payload["bot_running"] = bool(getattr(bot_service, "is_running", False))

        if sync_engine is not None and hasattr(sync_engine, "get_status"):
            try:
                sync_status = sync_engine.get_status()
                payload["git_synced"] = bool(getattr(sync_status, "is_synced", True))
                if hasattr(sync_status, "last_sync_time") and sync_status.last_sync_time:
                    payload["last_sync_time"] = sync_status.last_sync_time.isoformat()
            except Exception as e:
                logger.debug(f"Error querying sync engine status for health payload: {e}")

        return web.json_response(payload, status=200)

    async def metrics_handler(request: web.Request) -> web.Response:
        """
        GET /metrics
        Returns 200 OK with uptime, memory/config counters, and sync intervals.
        """
        now = datetime.now(timezone.utc)
        uptime = (now - start_time).total_seconds()
        payload: Dict[str, Any] = {
            "uptime_seconds": uptime,
            "sync_interval": config.auto_sync_interval_seconds,
            "port": config.port,
            "environment": config.environment,
            "model": config.llm_model,
            "provider": config.llm_provider,
        }
        return web.json_response(payload, status=200)

    async def root_handler(request: web.Request) -> web.Response:
        """
        GET /
        Friendly root ping.
        """
        return web.json_response(
            {
                "service": "OpenHuman & Hermes Autonomous Companion",
                "health": "/health",
                "metrics": "/metrics",
            },
            status=200,
        )

    # Routes
    app.router.add_get("/", root_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/metrics", metrics_handler)

    return app


async def start_health_server(
    config: Config,
    app: Optional[web.Application] = None,
    bot_service: Optional[Any] = None,
    sync_engine: Optional[Any] = None,
) -> Tuple[web.AppRunner, web.TCPSite]:
    """
    Start the async aiohttp health server bound to config.host and config.port.

    Returns:
        Tuple of (AppRunner, TCPSite).
    """
    if app is None:
        app = create_health_app(config, bot_service=bot_service, sync_engine=sync_engine)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=config.host, port=config.port)
    await site.start()
    logger.info(f"HTTP Health & Metrics server listening on http://{config.host}:{config.port}")
    return runner, site
