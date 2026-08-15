"""
Continuous Daemon Entrypoint & Lifecycle Manager.

Co-schedules the Telegram bot service, HTTP health/keepalive server, and periodic
Git synchronization engine in a single asyncio event loop. Traps SIGTERM and SIGINT
signals for graceful shutdown with in-flight task draining and final Git commit/push flush.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import signal
import sys
from typing import Any, Optional

from bot.config import Config, load_config
from bot.health import create_health_app, start_health_server

logger = logging.getLogger(__name__)


class DaemonRunner:
    """
    Continuous runtime process orchestrator for the OpenHuman & Hermes companion.
    """

    def __init__(
        self,
        config: Config,
        bot_service: Optional[Any] = None,
        sync_engine: Optional[Any] = None,
        vault_manager: Optional[Any] = None,
        agent_pipeline: Optional[Any] = None,
        health_app: Optional[Any] = None,
    ) -> None:
        self.config = config
        self.bot_service = bot_service
        self.sync_engine = sync_engine
        self.vault_manager = vault_manager
        self.agent_pipeline = agent_pipeline
        self.health_app = health_app
        self.shutdown_event = asyncio.Event()
        self.is_flushed: bool = False
        self._health_runner: Optional[Any] = None
        self._sync_task: Optional[asyncio.Task] = None

    def request_shutdown(self) -> None:
        """Signal the daemon to initiate graceful shutdown."""
        logger.info("Shutdown requested. Setting shutdown event trigger...")
        self.shutdown_event.set()

    def _setup_signal_handlers(self) -> None:
        """Register OS signal handlers for graceful termination."""
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                try:
                    loop.add_signal_handler(sig, self.request_shutdown)
                except (NotImplementedError, RuntimeError, ValueError) as err:
                    logger.debug(f"Signal {sig} could not be attached directly: {err}")
        except Exception as e:
            logger.debug(f"Could not configure signal handlers: {e}")

    async def _periodic_sync_loop(self) -> None:
        """Background loop executing periodic Git synchronization."""
        interval = self.config.auto_sync_interval_seconds
        if interval <= 0 or not self.sync_engine:
            return

        logger.info(f"Starting background Git sync loop (interval: {interval}s)...")
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(interval)
                if self.shutdown_event.is_set():
                    break
                logger.debug("Executing scheduled periodic Git synchronization...")
                if hasattr(self.sync_engine, "sync_now"):
                    res = self.sync_engine.sync_now()
                    if inspect.isawaitable(res):
                        await res
                elif hasattr(self.sync_engine, "commit_and_push"):
                    res = self.sync_engine.commit_and_push("Scheduled background sync")
                    if inspect.isawaitable(res):
                        await res
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error during periodic Git sync: {e}", exc_info=True)

    async def run(self) -> None:
        """
        Main continuous loop. Co-schedules all services and awaits shutdown event.
        """
        logger.info("Initializing Continuous Daemon Runner...")
        self._setup_signal_handlers()

        # 1. Start HTTP Health & Metrics Keepalive Server if enabled
        if self.config.environment != "test":
            try:
                app = self.health_app or create_health_app(
                    self.config,
                    bot_service=self.bot_service,
                    sync_engine=self.sync_engine,
                )
                runner, _ = await start_health_server(
                    self.config,
                    app=app,
                    bot_service=self.bot_service,
                    sync_engine=self.sync_engine,
                )
                self._health_runner = runner
            except Exception as e:
                logger.warning(f"Could not start HTTP health server: {e}")

        # 2. Start Telegram Bot Service
        if self.bot_service:
            await self.bot_service.start()

        # 3. Start Periodic Git Sync Task
        if self.sync_engine and self.config.auto_sync_interval_seconds > 0:
            self._sync_task = asyncio.create_task(self._periodic_sync_loop())

        logger.info("OpenHuman & Hermes Daemon is running. Waiting for shutdown signal...")

        # 4. Await shutdown trigger
        await self.shutdown_event.wait()

        # 5. Execute Graceful Shutdown
        await self.graceful_shutdown()

    async def graceful_shutdown(self) -> None:
        """
        Drain in-flight requests, stop background loops, shutdown bot, and flush Git changes.
        """
        logger.info("Initiating graceful shutdown sequence...")

        # 1. Stop background sync loop
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        # 2. Stop Telegram Bot Service
        if self.bot_service:
            try:
                await self.bot_service.stop()
            except Exception as e:
                logger.error(f"Error stopping Telegram bot during shutdown: {e}")

        # 3. Final Git commit and push flush
        if self.sync_engine and hasattr(self.sync_engine, "commit_and_push"):
            try:
                logger.info("Executing final Git sync flush before process exit...")
                res = self.sync_engine.commit_and_push("Final shutdown sync")
                if inspect.isawaitable(res):
                    await res
            except Exception as e:
                logger.error(f"Error flushing Git repository during shutdown: {e}")

        # 4. Cleanup HTTP server
        if self._health_runner:
            try:
                await self._health_runner.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up health runner: {e}")
            finally:
                self._health_runner = None

        self.is_flushed = True
        logger.info("Graceful shutdown sequence completed successfully.")


async def async_main() -> None:
    """Async entrypoint for daemon execution."""
    config = load_config()

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    validation_errors = config.validate_for_production()
    if validation_errors:
        for err in validation_errors:
            logger.warning(f"Config warning: {err}")

    # Lazy-load components
    from bot.agent.pipeline import SplitBrainAgentPipeline
    from bot.telegram.bot import TelegramBotService
    from bot.vault.manager import VaultManager

    vault = VaultManager(config.vault_path)
    pipeline = SplitBrainAgentPipeline(config=config)

    # Optional Git Sync Engine if configured
    sync_engine = None
    if config.git_remote_url:
        try:
            from bot.git_sync.engine import GitSyncEngine
            sync_engine = GitSyncEngine(
                repo_path=config.vault_path,
                remote_url=config.git_remote_url,
                branch=config.git_branch,
                auth_token=config.git_auth_token,
                ssh_key=config.git_ssh_key,
                author_name=config.git_author_name,
                author_email=config.git_author_email,
            )
            await sync_engine.initialize_repo()
        except Exception as e:
            logger.warning(f"Could not initialize GitSyncEngine: {e}")

    bot = TelegramBotService(
        config=config,
        agent_pipeline=pipeline,
        vault_manager=vault,
        git_sync=sync_engine,
    )

    daemon = DaemonRunner(
        config=config,
        bot_service=bot,
        sync_engine=sync_engine,
        vault_manager=vault,
        agent_pipeline=pipeline,
    )

    await daemon.run()


def main() -> None:
    """CLI entrypoint."""
    try:
        asyncio.run(async_main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Process terminated by user/system.")


if __name__ == "__main__":
    main()
