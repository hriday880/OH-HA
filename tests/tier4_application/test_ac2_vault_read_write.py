"""
Acceptance Criterion 2 (AC 2) Test Suite.
Verifies: "A test script successfully verifies that the agent pipeline can read a sample note from a mock Obsidian vault directory and write a new note to it."
"""

from __future__ import annotations

from pathlib import Path
import pytest
from bot.config import Config
from bot.agent.pipeline import SplitBrainAgentPipeline
from bot.agent.providers import MockLLMProvider
from bot.agent.tools import ToolDefinition, ToolRegistry
from bot.vault.manager import VaultManager


class TestAC2VaultReadWrite:
    """Acceptance Criterion 2: Agent Reading from & Writing to Mock Obsidian Vault."""

    @pytest.mark.asyncio
    async def test_ac2_obsidian_vault_read_and_write(self, test_config: Config, mock_vault_dir: Path):
        """
        [AC 2 Core Test]
        Verifies that the agent pipeline can read an existing sample note from a mock Obsidian vault
        directory and write a new note to it, as well as append to daily logs.
        """
        vault = VaultManager(mock_vault_dir)

        # 1. Register vault tools in the agent tool registry
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="read_note",
                description="Read note from Obsidian vault",
                parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            ),
            lambda path: vault.read_note(path).raw_body,
        )
        registry.register(
            ToolDefinition(
                name="write_note",
                description="Write note to Obsidian vault",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "mode": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            ),
            lambda path, content, mode="overwrite", **kwargs: vault.write_note(path, content, mode=mode).path,
        )

        llm = MockLLMProvider()

        # Step 1: Agent reads sample note (40-projects/Project_Apollo.md)
        llm.queue_tool_call("read_note", {"path": "40-projects/Project_Apollo.md"}, call_id="call_read_apollo")
        # Step 2: Agent creates a new summary note (50-knowledge/Apollo_Architecture_Summary.md)
        llm.queue_tool_call(
            "write_note",
            {
                "path": "50-knowledge/Apollo_Architecture_Summary.md",
                "content": "# Apollo Architecture Summary\n\nCloud agent with Obsidian sync and Telegram frontend.",
                "mode": "overwrite",
            },
            call_id="call_write_summary",
        )
        # Step 3: Agent produces final conversational confirmation
        llm.queue_text_response("I have read Project Apollo and created the new summary note in your knowledge base.")

        pipeline = SplitBrainAgentPipeline(
            config=test_config,
            primary_provider=llm,
            tool_registry=registry,
        )

        # 2. Execute agent pipeline workflow
        result = await pipeline.process_message("Please summarize Project Apollo and save it as a new knowledge note.")

        # 3. Assertions on agent output
        assert result is not None
        assert "created the new summary note" in result.content
        assert len(result.tools_executed) == 2
        assert result.tools_executed[0].name == "read_note"
        assert result.tools_executed[1].name == "write_note"

        # 4. Assert disk state in mock Obsidian vault directory
        new_note_file = mock_vault_dir / "50-knowledge" / "Apollo_Architecture_Summary.md"
        assert new_note_file.is_file()
        content = new_note_file.read_text(encoding="utf-8")
        assert "Apollo Architecture Summary" in content
        assert "Cloud agent with Obsidian sync" in content

        # 5. Verify reading back the newly written note via VaultManager
        verified_note = vault.read_note("50-knowledge/Apollo_Architecture_Summary.md")
        assert verified_note.path == "50-knowledge/Apollo_Architecture_Summary.md"
        assert "Cloud agent with Obsidian sync" in verified_note.raw_body

    def test_ac2_direct_vault_read_and_append_daily_log(self, mock_vault_dir: Path):
        """Verify direct vault reading and appending to daily notes."""
        vault = VaultManager(mock_vault_dir)

        # Read existing note
        profile = vault.read_note("30-people/User_Profile.md")
        assert profile.metadata.title == "User Profile"
        assert "Alice" in profile.raw_body

        # Append to daily note
        daily_note = vault.append_daily_log("AC2 Verification Passed: Read & write operations verified.", date_str="2026-08-15")
        assert (mock_vault_dir / "10-daily" / "2026-08-15.md").is_file()
        assert "AC2 Verification Passed" in daily_note.content
