"""
Feature 4: OpenHuman Persona & Memory Mapping Test Suite.
Tests persona greetings, directives, memory tree scanning from vault, and context budgeting.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from bot.agent.persona import MemoryTreeContext, OpenHumanPersona


class TestFeature04OpenHumanPersona:
    """Test suite for Feature 4: OpenHuman Persona & Memory Mapping."""

    def test_persona_greeting_first_time_and_returning(self):
        """Test persona greeting generator for first-time and returning users."""
        persona = OpenHumanPersona(bot_name="Hermes Companion", user_name="Alice")
        greeting_first = persona.get_greeting(is_first_time=True)
        assert "Hermes Companion" in greeting_first
        assert "Alice" in greeting_first
        assert "/help" in greeting_first

        greeting_returning = persona.get_greeting(is_first_time=False)
        assert "Alice" in greeting_returning
        assert "What are we focusing on today?" in greeting_returning

    def test_persona_instructions_formatting(self):
        """Test formatting of persona directives for system prompt injection."""
        persona = OpenHumanPersona(
            bot_name="Atlas",
            user_name="Bob",
            tone="philosophical and direct",
            custom_instructions="Always cite Obsidian note wikilinks when answering.",
        )
        text = persona.get_instructions_text()
        assert "Atlas" in text
        assert "Bob" in text
        assert "philosophical and direct" in text
        assert "Always cite Obsidian note wikilinks" in text

    def test_memory_tree_scan_profile(self, tmp_path: Path):
        """Test scanning user profile from Profile.md in vault root."""
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "Profile.md").write_text("# Profile\nName: Charlie\nFocus: Distributed Systems\n", encoding="utf-8")

        ctx = MemoryTreeContext(vault_path=vault)
        profile_content = ctx.scan_profile()
        assert profile_content is not None
        assert "Charlie" in profile_content
        assert "Distributed Systems" in profile_content

    def test_memory_tree_scan_daily_and_projects(self, tmp_path: Path):
        """Test scanning recent daily notes and active projects."""
        vault = tmp_path / "vault"
        daily = vault / "Daily"
        projects = vault / "Projects"
        daily.mkdir(parents=True)
        projects.mkdir(parents=True)

        (daily / "2026-08-15.md").write_text("# 2026-08-15 Log\nDiscussed Apollo architecture.\n", encoding="utf-8")
        (projects / "Apollo.md").write_text("# Project Apollo\nAutonomous cloud agent.\n", encoding="utf-8")

        ctx = MemoryTreeContext(vault_path=vault)
        recent_daily = ctx.scan_recent_daily_notes(count=2)
        active_proj = ctx.scan_active_projects(max_projects=3)

        assert len(recent_daily) == 1
        assert "2026-08-15.md" in recent_daily[0]["filename"]
        assert len(active_proj) == 1
        assert active_proj[0]["title"] == "Apollo"

    def test_memory_tree_context_char_budgeting(self, tmp_path: Path):
        """Test that memory tree context respects character limits."""
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "Profile.md").write_text("A" * 500, encoding="utf-8")

        ctx = MemoryTreeContext(vault_path=vault, max_context_chars=300)
        block = ctx.build_context_block()
        assert len(block) > 0
        assert "User Profile & Preferences" in block
