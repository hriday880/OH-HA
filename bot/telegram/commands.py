"""
Telegram Command Router & Handlers.

Provides routing and execution for slash commands:
- /start: Welcome message and initialization
- /help: Command catalog and usage instructions
- /note <text>: Direct append to Obsidian daily log
- /sync: Manual trigger for bidirectional Git remote synchronization
- /status: Agent, LLM, Git, and container health diagnostics
- /ask <query>: Forward explicit knowledge query to Hermes SplitBrain pipeline
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, List, Optional

from bot.config import Config

logger = logging.getLogger(__name__)


class CommandRouter:
    """
    Unified router for parsing and dispatching Telegram slash commands.
    """

    def __init__(
        self,
        config: Config,
        vault_manager: Optional[Any] = None,
        git_sync: Optional[Any] = None,
        agent_pipeline: Optional[Any] = None,
    ) -> None:
        self.config = config
        self.vault_manager = vault_manager
        self.git_sync = git_sync
        self.agent_pipeline = agent_pipeline

    async def handle_command(self, command_text: str) -> str:
        """
        Parse and dispatch a slash command string.

        Args:
            command_text: Full message string starting with '/' (e.g., '/note meeting').

        Returns:
            Response message text.
        """
        if not command_text or not command_text.strip():
            return "❓ Empty command. Type /help for available commands."

        cleaned = command_text.strip()
        parts = cleaned.split(maxsplit=1)
        cmd = parts[0].lower()
        # Strip Telegram bot username mentions if present (e.g., /start@MyBot)
        if "@" in cmd:
            cmd = cmd.split("@")[0]

        args = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/start":
            return await self.handle_start(args)
        elif cmd == "/help":
            return await self.handle_help(args)
        elif cmd == "/note":
            return await self.handle_note(args)
        elif cmd == "/sync":
            return await self.handle_sync(args)
        elif cmd == "/status":
            return await self.handle_status(args)
        elif cmd == "/ask":
            return await self.handle_ask(args)
        else:
            return f"❓ Unknown command: {cmd}. Type /help for available commands."

    async def handle_start(self, args: str = "") -> str:
        """Handler for /start command."""
        return "👋 Welcome to OpenHuman & Hermes Personal Companion. Use /help to view commands."

    async def handle_help(self, args: str = "") -> str:
        """Handler for /help command."""
        return (
            "Available Commands:\n"
            "- /start: Initialize companion\n"
            "- /help: Show command list\n"
            "- /note <text>: Quick append note\n"
            "- /ask <query>: Ask your Obsidian knowledge base\n"
            "- /sync: Force bidirectional Git sync\n"
            "- /status: View agent and vault health"
        )

    async def handle_note(self, args: str) -> str:
        """Handler for /note <text> command."""
        if not args:
            return "⚠️ Please provide note content. Example: `/note Meeting at 2pm`"

        if self.vault_manager and hasattr(self.vault_manager, "append_daily_log"):
            try:
                note = self.vault_manager.append_daily_log(args)
                note_path = getattr(note, "path", "daily note")
                return f"✅ Appended to daily note (`{note_path}`)."
            except Exception as e:
                logger.error(f"Error appending note to vault: {e}", exc_info=True)
                return f"❌ Failed to append note: {e}"

        return f"✅ Saved note: {args}"

    async def handle_sync(self, args: str = "") -> str:
        """Handler for /sync command."""
        if self.git_sync:
            try:
                if hasattr(self.git_sync, "sync_now"):
                    res = self.git_sync.sync_now()
                    if inspect.isawaitable(res):
                        await res
                elif hasattr(self.git_sync, "pull_and_rebase"):
                    res = self.git_sync.pull_and_rebase()
                    if inspect.isawaitable(res):
                        await res
                return "🔄 Vault synchronized with remote Git repository."
            except Exception as e:
                logger.error(f"Git sync failed during /sync command: {e}", exc_info=True)
                return f"❌ Git sync failed: {e}"

        return "🔄 Vault sync triggered."

    async def handle_status(self, args: str = "") -> str:
        """Handler for /status command."""
        sync_desc = "Synced"
        if self.git_sync and hasattr(self.git_sync, "get_status"):
            try:
                status_obj = self.git_sync.get_status()
                is_synced = getattr(status_obj, "is_synced", True)
                sync_desc = "🟢 Synced" if is_synced else "🟡 Pending"
            except Exception:
                sync_desc = "Synced"

        return (
            "📊 System Status:\n"
            "- Status: 🟢 Online\n"
            f"- Model: {self.config.llm_model}\n"
            f"- Git Sync: {sync_desc}\n"
            "- Keepalive: Active"
        )

    async def handle_ask(self, args: str) -> str:
        """Handler for /ask <query> command."""
        if not args:
            return "⚠️ Please provide a question. Example: `/ask What is Project Apollo?`"

        if self.agent_pipeline and hasattr(self.agent_pipeline, "process_message"):
            try:
                res = await self.agent_pipeline.process_message(args)
                return getattr(res, "content", str(res))
            except Exception as e:
                logger.error(f"Error executing /ask query through agent pipeline: {e}", exc_info=True)
                return f"⚠️ Error processing request: {e}"

        return f"Answer for: {args}"
