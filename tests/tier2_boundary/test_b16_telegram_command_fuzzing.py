"""
Boundary Test 16: Telegram Command Fuzzing & Malformed Arguments.
Tests command parser with huge arguments, casing variations, extra whitespace, and symbols.
"""

from __future__ import annotations

import pytest
from bot.config import Config
from bot.telegram.commands import CommandRouter


class TestBoundary16TelegramCommandFuzzing:
    """Boundary tests for Feature 16 (Telegram Commands)."""

    @pytest.mark.asyncio
    async def test_case_insensitive_command_dispatch(self, test_config: Config):
        """Test slash commands handle uppercase and mixed-case inputs gracefully."""
        router = CommandRouter(config=test_config)

        res1 = await router.handle_command("/HELP")
        assert "Available Commands" in res1

        res2 = await router.handle_command("/StArT")
        assert "Welcome" in res2

        res3 = await router.handle_command("/STATUS")
        assert "System Status" in res3

    @pytest.mark.asyncio
    async def test_oversized_note_command_argument(self, test_config: Config):
        """Test /note with 10,000 character argument."""
        router = CommandRouter(config=test_config)
        huge_note = "/note " + ("Important thought " * 500)

        res = await router.handle_command(huge_note)
        assert "Saved note" in res or "Appended" in res

    @pytest.mark.asyncio
    async def test_leading_and_trailing_whitespace_stripping(self, test_config: Config):
        """Test commands with excessive surrounding whitespace."""
        router = CommandRouter(config=test_config)

        res = await router.handle_command("    /help    ")
        assert "Available Commands" in res

    @pytest.mark.asyncio
    async def test_ask_command_with_special_symbols(self, test_config: Config):
        """Test /ask query with symbols and quotes."""
        router = CommandRouter(config=test_config)
        res = await router.handle_command('/ask "Project Apollo" & <Quantum> $100!')
        assert "Apollo" in res
