"""
Tier 2 Boundary Tests: Feature 4 - OpenHuman Persona & Memory Tree Context Builder.
"""

import tempfile
import unittest
from pathlib import Path

from bot.agent.persona import MemoryTreeContext, OpenHumanPersona


class TestPersonaBoundary(unittest.TestCase):
    """Tier 2 Boundary tests for persona and memory context."""

    def test_nonexistent_vault_directory_graceful_fallback(self):
        """Test MemoryTreeContext handling non-existent vault path."""
        ctx = MemoryTreeContext(vault_path=Path("/tmp/nonexistent_vault_path_12345"))
        self.assertIsNone(ctx.scan_profile())
        self.assertEqual(ctx.scan_recent_daily_notes(), [])
        self.assertEqual(ctx.scan_active_projects(), [])
        self.assertEqual(ctx.list_memory_folders(), [])
        block = ctx.build_context_block()
        self.assertIn("Fresh memory workspace", block)

    def test_empty_vault_directory(self):
        """Test MemoryTreeContext in an empty folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = MemoryTreeContext(vault_path=Path(tmpdir))
            self.assertIsNone(ctx.scan_profile())
            block = ctx.build_context_block()
            self.assertIn("Fresh memory workspace", block)

    def test_context_char_budget_enforcement(self):
        """Test that memory block respects strict character budget."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "Profile.md").write_text("A" * 500, encoding="utf-8")
            (p / "Daily").mkdir()
            (p / "Daily" / "2026-08-14.md").write_text("B" * 500, encoding="utf-8")

            # Budget allows only profile
            ctx = MemoryTreeContext(vault_path=p, max_context_chars=600)
            block = ctx.build_context_block()
            self.assertLessEqual(len(block), 700)
            self.assertIn("User Profile & Preferences", block)

    def test_persona_custom_instructions_none(self):
        """Test persona without custom instructions."""
        persona = OpenHumanPersona(custom_instructions=None)
        text = persona.get_instructions_text()
        self.assertNotIn("Custom Persona Directives", text)


if __name__ == "__main__":
    unittest.main()
