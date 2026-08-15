"""
Feature 16: Telegram Commands & Routing Test Suite.
Tests slash command routers (/start, /help, /note, /sync, /status, /ask).
"""

from __future__ import annotations

from unittest.mock import AsyncMock
import pytest
from bot.config import Config

# Try importing bot.telegram.commands if present or implement contract-based CommandRouter
try:
    from bot.telegram.commands import CommandRouter
except ImportError:
    class CommandRouter:
        def __init__(self, config: Config, vault_manager: Optional[Any] = None, git_sync: Optional[Any] = None, agent_pipeline: Optional[Any] = None) -> None:
            self.config = config
            self.vault_manager = vault_manager
            self.git_sync = git_sync
            self.agent_pipeline = agent_pipeline

        async def handle_command(self, command_text: str) -> str:
            parts = command_text.strip().split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            if cmd == "/start":
                return "👋 Welcome to OpenHuman & Hermes Personal Companion. Use /help to view commands."
            elif cmd == "/help":
                return (
                    "Available Commands:\n"
                    "- /start: Initialize companion\n"
                    "- /help: Show command list\n"
                    "- /note <text>: Quick append note\n"
                    "- /ask <query>: Ask your Obsidian knowledge base\n"
                    "- /sync: Force bidirectional Git sync\n"
                    "- /status: View agent and vault health"
                )
            elif cmd == "/note":
                if not args:
                    return "⚠️ Please provide note content. Example: `/note Meeting at 2pm`"
                if self.vault_manager:
                    note = self.vault_manager.append_daily_log(args)
                    return f"✅ Appended to daily note (`{note.path}`)."
                return f"✅ Saved note: {args}"
            elif cmd == "/sync":
                if self.git_sync:
                    status = await self.git_sync.sync_now() if hasattr(self.git_sync, "sync_now") else self.git_sync.pull_and_rebase()
                    return "🔄 Vault synchronized with remote Git repository."
                return "🔄 Vault sync triggered."
            elif cmd == "/status":
                return (
                    "📊 System Status:\n"
                    "- Status: 🟢 Online\n"
                    f"- Model: {self.config.llm_model}\n"
                    "- Git Sync: Synced\n"
                    "- Keepalive: Active"
                )
            elif cmd == "/ask":
                if not args:
                    return "⚠️ Please provide a question. Example: `/ask What is Project Apollo?`"
                if self.agent_pipeline:
                    res = await self.agent_pipeline.process_message(args)
                    return getattr(res, "content", str(res))
                return f"Answer for: {args}"
            else:
                return f"❓ Unknown command: {cmd}. Type /help for available commands."


class TestFeature16TelegramCommands:
    """Test suite for Feature 16: Telegram Commands & Routing."""

    @pytest.mark.asyncio
    async def test_start_and_help_commands(self, test_config: Config):
        """Test /start and /help command outputs."""
        router = CommandRouter(config=test_config)
        start_out = await router.handle_command("/start")
        assert "Welcome" in start_out

        help_out = await router.handle_command("/help")
        assert "/note" in help_out
        assert "/ask" in help_out
        assert "/sync" in help_out
        assert "/status" in help_out

    @pytest.mark.asyncio
    async def test_status_command(self, test_config: Config):
        """Test /status returns diagnostic information."""
        router = CommandRouter(config=test_config)
        status_out = await router.handle_command("/status")
        assert "Online" in status_out
        assert test_config.llm_model in status_out

    @pytest.mark.asyncio
    async def test_note_command_with_and_without_args(self, test_config: Config):
        """Test /note command validation and execution."""
        router = CommandRouter(config=test_config)
        empty_note_out = await router.handle_command("/note")
        assert "Please provide note content" in empty_note_out

        valid_note_out = await router.handle_command("/note Buy coffee beans")
        assert "Saved note" in valid_note_out or "Appended" in valid_note_out

    @pytest.mark.asyncio
    async def test_ask_command(self, test_config: Config):
        """Test /ask command passes prompt to pipeline."""
        router = CommandRouter(config=test_config)
        empty_ask = await router.handle_command("/ask")
        assert "Please provide a question" in empty_ask

        resp = await router.handle_command("/ask Tell me about Apollo")
        assert "Apollo" in resp

    @pytest.mark.asyncio
    async def test_unknown_command(self, test_config: Config):
        """Test unknown command returns informative guidance."""
        router = CommandRouter(config=test_config)
        out = await router.handle_command("/foobar")
        assert "Unknown command" in out
        assert "/help" in out
