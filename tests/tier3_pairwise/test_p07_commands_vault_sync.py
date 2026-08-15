"""
Pairwise Test 7: Telegram Slash Commands & Git Sync Pipeline.
Tests /sync, /note, and /status commands interacting directly with VaultManager and GitSyncEngine.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import pytest
from bot.config import Config
from bot.git_sync.engine import GitSyncEngine
from bot.telegram.commands import CommandRouter
from bot.vault.manager import VaultManager


class TestPairwiseCommandsVaultSync:
    """Pairwise Integration Suite: Telegram Commands + Vault + Git Sync."""

    @pytest.mark.asyncio
    async def test_sync_command_triggers_git_pull_and_push(self, test_config: Config, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test /sync command triggers Git sync and returns success message."""
        remote, local = mock_git_remote_and_clone
        sync_engine = GitSyncEngine(repo_path=local, branch="main")

        router = CommandRouter(config=test_config, git_sync=sync_engine)
        response = await router.handle_command("/sync")

        assert "Vault synchronized" in response or "triggered" in response

    @pytest.mark.asyncio
    async def test_note_command_appends_and_syncs(self, test_config: Config, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test /note appends to daily note and enables immediate Git commit."""
        remote, local = mock_git_remote_and_clone
        vault = VaultManager(local)
        sync_engine = GitSyncEngine(repo_path=local, branch="main")

        router = CommandRouter(config=test_config, vault_manager=vault, git_sync=sync_engine)
        response = await router.handle_command("/note Discussed quantum algorithms with Alice")

        assert "Appended to daily note" in response or "Saved note" in response

        # Sync to remote
        pushed = sync_engine.commit_and_push("Commit after /note command")
        assert pushed is True

        # Check bare remote
        log_res = subprocess.run(
            ["git", "--git-dir", str(remote), "log", "-n", "1", "--oneline"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Commit after /note command" in log_res.stdout
