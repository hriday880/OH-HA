"""
Tier 1 Feature Tests: Feature 4 - OpenHuman Persona & Memory Tree Context Builder.
"""

import unittest
from pathlib import Path

from bot.agent.persona import MemoryTreeContext, OpenHumanPersona
from tests.conftest import create_temp_vault, cleanup_temp_vault


class TestPersonaFeature(unittest.TestCase):
    """Tier 1 Unit tests for OpenHuman persona and memory tree context generation."""

    def setUp(self):
        self.vault_path = create_temp_vault()

    def tearDown(self):
        cleanup_temp_vault(self.vault_path)

    def test_persona_greetings(self):
        """Test initial and returning persona greetings."""
        persona = OpenHumanPersona(bot_name="OpenHuman", user_name="Bob")
        g1 = persona.get_greeting(is_first_time=True)
        self.assertIn("Bob", g1)
        self.assertIn("OpenHuman", g1)
        self.assertIn("/help", g1)

        g2 = persona.get_greeting(is_first_time=False)
        self.assertIn("Bob", g2)

    def test_persona_instructions_text(self):
        """Test formatting persona system prompt directives."""
        persona = OpenHumanPersona(
            bot_name="HermesCompanion",
            user_name="Carol",
            tone="proactive and sharp",
            custom_instructions="Always include relevant tags.",
        )
        text = persona.get_instructions_text()
        self.assertIn("HermesCompanion", text)
        self.assertIn("Carol", text)
        self.assertIn("proactive and sharp", text)
        self.assertIn("Always include relevant tags.", text)

    def test_memory_context_scan_profile(self):
        """Test extracting user profile from Profile.md."""
        ctx = MemoryTreeContext(vault_path=self.vault_path)
        profile = ctx.scan_profile()
        self.assertIsNotNone(profile)
        self.assertIn("TestUser", profile)
        self.assertIn("AI Agents", profile)

    def test_memory_context_scan_daily_notes(self):
        """Test retrieving recent daily notes."""
        ctx = MemoryTreeContext(vault_path=self.vault_path)
        daily_notes = ctx.scan_recent_daily_notes(count=2)
        self.assertEqual(len(daily_notes), 1)
        self.assertEqual(daily_notes[0]["filename"], "2026-08-14.md")
        self.assertIn("Refactored LLM provider adapters", daily_notes[0]["snippet"])

    def test_memory_context_scan_active_projects(self):
        """Test scanning active projects from Projects/ directory."""
        ctx = MemoryTreeContext(vault_path=self.vault_path)
        projects = ctx.scan_active_projects(max_projects=3)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["title"], "HermesAgent")
        self.assertIn("Multi-step reasoning engine", projects[0]["snippet"])

    def test_memory_context_build_full_block(self):
        """Test assembling full memory tree block."""
        ctx = MemoryTreeContext(vault_path=self.vault_path)
        block = ctx.build_context_block()
        self.assertIn("User Profile & Preferences", block)
        self.assertIn("Recent Daily Activity", block)
        self.assertIn("Active Projects", block)


if __name__ == "__main__":
    unittest.main()
