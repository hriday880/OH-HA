"""
Telegram Async Bot Service.

Provides the core Telegram bot lifecycle using python-telegram-bot v20+ async runner,
long-polling update consumer with drop_pending_updates=True, typing indicator heartbeat,
and natural conversation message routing to SplitBrainAgentPipeline.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Union

from bot.config import Config
from bot.telegram.commands import CommandRouter
from bot.telegram.formatters import chunk_message, escape_markdown_v2
from bot.telegram.security import is_user_authorized, log_unauthorized_access

logger = logging.getLogger(__name__)

# Attempt importing python-telegram-bot components
try:
    from telegram import Update
    from telegram.constants import ChatAction, ParseMode
    from telegram.error import NetworkError, RetryAfter, TelegramError
    from telegram.ext import (
        Application,
        ApplicationBuilder,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
    HAS_PTB = True
except ImportError:
    HAS_PTB = False
    Application = Any  # type: ignore
    Update = Any  # type: ignore
    ContextTypes = Any  # type: ignore


class TelegramBotService:
    """
    Async Telegram Bot Service coordinating polling lifecycle, command routing,
    and Split-Brain agent conversation processing.
    """

    def __init__(
        self,
        config: Config,
        agent_pipeline: Optional[Any] = None,
        vault_manager: Optional[Any] = None,
        git_sync: Optional[Any] = None,
    ) -> None:
        self.config = config
        self.agent_pipeline = agent_pipeline
        self.vault_manager = vault_manager
        self.git_sync = git_sync
        self.command_router = CommandRouter(
            config=config,
            vault_manager=vault_manager,
            git_sync=git_sync,
            agent_pipeline=agent_pipeline,
        )
        self.is_running: bool = False
        self.drop_pending_updates: bool = True
        self._app: Optional[Any] = None
        self._polling_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """
        Start the Telegram Bot service and initialize long polling.
        """
        self.is_running = True
        logger.info("Starting Telegram Bot Service...")

        has_token = bool(self.config.telegram_bot_token)
        env_val = self.config.environment
        logger.info(f"DEBUG-STARTUP: token_present={has_token}, HAS_PTB={HAS_PTB}, env={env_val}")

        # If a real token is provided and PTB is installed, start live polling
        if self.config.telegram_bot_token and HAS_PTB and self.config.environment != "test":
            try:
                self._app = (
                    ApplicationBuilder()
                    .token(self.config.telegram_bot_token)
                    .build()
                )
                self._register_handlers(self._app)

                await self._app.initialize()
                await self._app.start()

                if self._app.updater:
                    await self._app.updater.start_polling(
                        drop_pending_updates=self.drop_pending_updates,
                        allowed_updates=["message", "edited_message", "callback_query"],
                    )
                logger.info("Telegram Bot long-polling initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to start live Telegram polling: {e}", exc_info=True)
                # Keep is_running = True to allow graceful recovery or test mock interactions
        else:
            logger.info("Telegram Bot started in mock/offline mode (no active polling token).")

    async def stop(self) -> None:
        """
        Stop the Telegram Bot service cleanly, draining any in-flight updates.
        """
        logger.info("Stopping Telegram Bot Service...")
        self.is_running = False

        if self._app is not None and HAS_PTB:
            try:
                if self._app.updater and self._app.updater.is_running:
                    await self._app.updater.stop()
                if self._app.is_running:
                    await self._app.stop()
                await self._app.shutdown()
            except Exception as e:
                logger.warning(f"Error during Telegram Bot shutdown: {e}")
            finally:
                self._app = None

        logger.info("Telegram Bot Service stopped.")

    async def process_user_message(self, user_id: int, text: str) -> str:
        """
        Direct message processing entrypoint.

        Performs:
        1. Lifecycle state check (raises RuntimeError if not running)
        2. Whitelist authorization verification
        3. Slash command vs natural conversation triage and execution

        Args:
            user_id: Telegram user ID.
            text: Inbound message text.

        Returns:
            Generated response text.
        """
        if not self.is_running:
            raise RuntimeError("Bot is not running.")

        # Authorization check
        if not self._check_authorization(user_id, action=text):
            return "⛔ Unauthorized access. Your Telegram user ID is not authorized."

        # Slash command dispatch
        cleaned = text.strip() if text else ""
        if cleaned.startswith("/"):
            return await self.command_router.handle_command(cleaned)

        # Natural conversation dispatch to Agent Pipeline
        if self.agent_pipeline:
            try:
                res = await self.agent_pipeline.process_message(cleaned)
                return getattr(res, "content", str(res))
            except Exception as e:
                logger.error(f"Agent pipeline execution error: {e}", exc_info=True)
                return f"⚠️ Error processing request: {e}"

        return f"Processed: {text}"

    def _check_authorization(self, user_id: int, action: Optional[str] = None) -> bool:
        """Check if user_id is authorized on whitelist."""
        if not self.config.allowed_telegram_user_ids:
            return True

        authorized = int(user_id) in self.config.allowed_telegram_user_ids
        if not authorized:
            log_unauthorized_access(user_id=user_id, action=action)
        return authorized

    def _register_handlers(self, app: Any) -> None:
        """Register command and message handlers with python-telegram-bot Application."""
        if not HAS_PTB or app is None:
            return

        # Commands
        for cmd in ["start", "help", "note", "sync", "status", "ask"]:
            app.add_handler(CommandHandler(cmd, self._ptb_command_handler))

        # Natural conversation handler
        app.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), self._ptb_message_handler)
        )

    async def _ptb_command_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler for slash commands received via live Telegram webhook/polling."""
        if not update.effective_user or not update.effective_message:
            return

        user_id = update.effective_user.id
        chat_id = update.effective_chat.id if update.effective_chat else user_id
        text = update.effective_message.text or ""

        if not self._check_authorization(user_id, action=text):
            await update.effective_message.reply_text("⛔ Unauthorized access.")
            return

        # Run with typing indicator heartbeat
        response_text = await self._run_with_typing_heartbeat(
            chat_id=chat_id,
            coroutine=self.command_router.handle_command(text),
            context=context,
        )

        await self._send_chunked_reply(update, response_text)

    async def _ptb_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler for regular text messages received via live Telegram webhook/polling."""
        if not update.effective_user or not update.effective_message:
            return

        user_id = update.effective_user.id
        chat_id = update.effective_chat.id if update.effective_chat else user_id
        text = update.effective_message.text or ""

        if not self._check_authorization(user_id, action=text):
            await update.effective_message.reply_text("⛔ Unauthorized access.")
            return

        # Route through agent pipeline with typing indicator heartbeat
        async def _execute() -> str:
            if self.agent_pipeline:
                res = await self.agent_pipeline.process_message(text)
                return getattr(res, "content", str(res))
            return f"Processed: {text}"

        response_text = await self._run_with_typing_heartbeat(
            chat_id=chat_id,
            coroutine=_execute(),
            context=context,
        )

        await self._send_chunked_reply(update, response_text)

    async def _run_with_typing_heartbeat(
        self,
        chat_id: int,
        coroutine: Any,
        context: Optional[ContextTypes.DEFAULT_TYPE] = None,
    ) -> str:
        """
        Execute an async operation while sending a periodic Telegram typing indicator.
        """
        async def _heartbeat() -> None:
            while True:
                try:
                    if context and hasattr(context, "bot"):
                        await context.bot.send_chat_action(
                            chat_id=chat_id,
                            action=ChatAction.TYPING if HAS_PTB else "typing",
                        )
                except Exception:
                    pass
                await asyncio.sleep(4.5)

        heartbeat_task = asyncio.create_task(_heartbeat())
        try:
            return await coroutine
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _send_chunked_reply(self, update: Update, text: str) -> None:
        """
        Send a response split into chunks <= 4096 characters with error recovery.
        """
        if not update.effective_message:
            return

        chunks = chunk_message(text)
        for chunk in chunks:
            try:
                await update.effective_message.reply_text(chunk)
            except Exception as e:
                # If Telegram rate limit occurs, backoff and retry
                if HAS_PTB and isinstance(e, RetryAfter):
                    await asyncio.sleep(e.retry_after + 0.5)
                    await update.effective_message.reply_text(chunk)
                else:
                    logger.error(f"Failed to send message chunk: {e}")


# Alias for interface compatibility
TelegramBot = TelegramBotService
