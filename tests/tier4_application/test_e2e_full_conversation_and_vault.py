"""
Tier 4 Application Scenario 5: Full Conversation, Tool Execution & Git Push Lifecycle.
Tests multi-turn Telegram dialogue -> Hermes search & read -> Conversation capture -> Remote Git Push.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
from typing import Any
import pytest
from bot.config import Config
from bot.agent.pipeline import SplitBrainAgentPipeline
from bot.agent.providers import MockLLMProvider
from bot.agent.tools import ToolDefinition, ToolRegistry
from bot.git_sync.engine import GitSyncEngine
from bot.vault.manager import VaultManager
from bot.vault.search import VaultSearchEngine


class TestE2EFullConversationAndVault:
    """End-to-End User Scenario: Full Conversation & Remote Vault Sync Lifecycle."""

    @pytest.mark.asyncio
    async def test_e2e_full_conversation_and_vault_lifecycle(
        self,
        test_config: Config,
        bare_git_remote: Path,
        mock_telegram_app: Any,
        tmp_path: Path,
    ):
        """
        Complete E2E workflow:
        1. Agent starts with clone of bare remote repository.
        2. User sends query over Telegram: "What are my goals for 2026?"
        3. Agent invokes search_notes tool -> finds User_Profile.md -> reads it.
        4. Agent answers with user goals from vault.
        5. Agent logs conversation session into 20-conversations/ folder.
        6. Agent commits and pushes session log to remote Git repository.
        """
        # 1. Clone remote repo into agent working directory
        agent_vault = tmp_path / "agent_vault"
        subprocess.run(["git", "clone", str(bare_git_remote), str(agent_vault)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(agent_vault), "config", "user.name", "Hermes Agent"], check=True)
        subprocess.run(["git", "-C", str(agent_vault), "config", "user.email", "agent@openhuman.local"], check=True)

        # Populate profile note
        (agent_vault / "30-people").mkdir(parents=True, exist_ok=True)
        (agent_vault / "30-people" / "User_Profile.md").write_text(
            "---\ntitle: User Profile\n---\n# Profile\nGoals for 2026: Launch Project Apollo, master Rust.\n",
            encoding="utf-8",
        )
        (agent_vault / "20-conversations").mkdir(parents=True, exist_ok=True)

        vault = VaultManager(agent_vault)
        search_engine = VaultSearchEngine(agent_vault)
        sync_engine = GitSyncEngine(repo_path=agent_vault, branch="main")

        # 2. Tool Registry
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="search_notes", description="Search", parameters={"type": "object", "properties": {"query": {"type": "string"}}}),
            lambda query: search_engine.search(query),
        )
        registry.register(
            ToolDefinition(name="read_note", description="Read", parameters={"type": "object", "properties": {"path": {"type": "string"}}}),
            lambda path: vault.read_note(path).raw_body,
        )
        registry.register(
            ToolDefinition(
                name="write_note",
                description="Write",
                parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
            ),
            lambda path, content, **kwargs: vault.write_note(path, content, mode="overwrite").path,
        )

        # 3. LLM simulation
        llm = MockLLMProvider()
        # Step 1: LLM searches for goals
        llm.queue_tool_call("search_notes", {"query": "Goals 2026"}, call_id="c1")
        # Step 2: LLM reads profile
        llm.queue_tool_call("read_note", {"path": "30-people/User_Profile.md"}, call_id="c2")
        # Step 3: LLM logs session
        llm.queue_tool_call(
            "write_note",
            {
                "path": "20-conversations/2026-08-15-goals-review.md",
                "content": "# Goals Review\nUser asked for 2026 goals: Launch Project Apollo, master Rust.",
            },
            call_id="c3",
        )
        # Step 4: Final response
        llm.queue_text_response("Your primary goals for 2026 are: Launch Project Apollo and master Rust.")

        pipeline = SplitBrainAgentPipeline(
            config=test_config,
            primary_provider=llm,
            tool_registry=registry,
        )

        # 4. User sends message via Telegram
        await mock_telegram_app.send_chat_action(chat_id=123456789, action="typing")
        result = await pipeline.process_message("What are my goals for 2026?")
        await mock_telegram_app.send_message(chat_id=123456789, text=result.content)

        # 5. Git Sync Engine commits and pushes
        pushed = sync_engine.commit_and_push("Capture conversation 2026-08-15-goals-review")
        assert pushed is True

        # 6. Verifications
        assert "Launch Project Apollo and master Rust" in result.content
        assert len(mock_telegram_app.sent_messages) == 1
        assert "Project Apollo" in mock_telegram_app.sent_messages[0]["text"]
        assert (agent_vault / "20-conversations" / "2026-08-15-goals-review.md").is_file()

        # Remote bare repo verification
        log_res = subprocess.run(
            ["git", "--git-dir", str(bare_git_remote), "log", "-n", "1", "--oneline"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Capture conversation" in log_res.stdout
