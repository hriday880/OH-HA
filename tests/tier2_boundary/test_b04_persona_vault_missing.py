"""
Boundary Test 4: Persona & Missing Vault Folders.
Tests memory context builder when folders (Daily, Projects, Profile) are absent or empty.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from bot.agent.persona import MemoryTreeContext, OpenHumanPersona


class TestBoundary04PersonaMissingVault:
    """Boundary tests for Feature 4 (OpenHuman Persona & Memory)."""

    def test_nonexistent_vault_directory_handling(self, tmp_path: Path):
        """Test MemoryTreeContext handles non-existent vault path without throwing unhandled exceptions."""
        nonexistent = tmp_path / "does_not_exist_vault"
        ctx = MemoryTreeContext(vault_path=nonexistent)

        assert ctx.scan_profile() is None
        assert ctx.scan_recent_daily_notes() == []
        assert ctx.scan_active_projects() == []
        assert ctx.list_memory_folders() == []

        block = ctx.build_context_block()
        assert "Fresh memory workspace" in block

    def test_empty_vault_directory(self, tmp_path: Path):
        """Test empty vault directory produces clean fallback context."""
        empty_vault = tmp_path / "empty_vault"
        empty_vault.mkdir()

        ctx = MemoryTreeContext(vault_path=empty_vault)
        block = ctx.build_context_block()
        assert "Fresh memory workspace" in block

    def test_profile_with_empty_content(self, tmp_path: Path):
        """Test Profile.md with zero bytes returns None."""
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "Profile.md").write_text("   \n", encoding="utf-8")

        ctx = MemoryTreeContext(vault_path=vault)
        assert ctx.scan_profile() is None

    def test_extreme_character_budget_truncation(self, tmp_path: Path):
        """Test context generator with extremely small char budget (50 chars)."""
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "Profile.md").write_text("# Alice\nLots of profile info...", encoding="utf-8")

        ctx = MemoryTreeContext(vault_path=vault, max_context_chars=50)
        block = ctx.build_context_block()
        assert isinstance(block, str)

    def test_persona_custom_instructions_none(self):
        """Test persona formatting with None custom instructions."""
        persona = OpenHumanPersona(custom_instructions=None)
        instructions = persona.get_instructions_text()
        assert "Custom Persona Directives" not in instructions
        assert "OpenHuman" in instructions
