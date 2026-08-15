"""
Pairwise Test 3: Obsidian Vault Manager & Remote Git Synchronization.
Tests local note creation triggering debounced Git commit and push to bare remote repository.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
import pytest
from bot.git_sync.engine import DebouncedPushQueue, GitSyncEngine
from bot.vault.manager import VaultManager


class TestPairwiseVaultGitSync:
    """Pairwise Integration Suite: Vault Manager + Git Sync Engine."""

    @pytest.mark.asyncio
    async def test_vault_write_triggers_git_commit_and_push(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test note created in local clone is pushed to bare remote via debounced sync."""
        remote, local = mock_git_remote_and_clone
        vault = VaultManager(local)
        sync_engine = GitSyncEngine(repo_path=local, branch="main")

        async def push_handler(count: int):
            sync_engine.commit_and_push("Debounced push after vault writes")

        queue = DebouncedPushQueue(debounce_seconds=0.05, push_callback=push_handler)

        # 1. Write note
        note = vault.write_note("50-knowledge/Cloud_Containers.md", "# Cloud Containers\nDocker and Tini setup.", mode="overwrite")
        assert (local / "50-knowledge" / "Cloud_Containers.md").is_file()

        # 2. Enqueue for push
        await queue.enqueue(note.path)

        # 3. Await debounce flush
        await asyncio.sleep(0.1)

        # 4. Assert remote bare repo has the commit
        log_res = subprocess.run(
            ["git", "--git-dir", str(remote), "log", "-n", "1", "--oneline"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Debounced push" in log_res.stdout

    @pytest.mark.asyncio
    async def test_daily_log_append_sync(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test daily log appends synced to remote repository."""
        remote, local = mock_git_remote_and_clone
        vault = VaultManager(local)
        sync_engine = GitSyncEngine(repo_path=local, branch="main")

        note = vault.append_daily_log("Logged entry for sync test", date_str="2026-08-15")
        sync_engine.commit_and_push("Update daily log 2026-08-15")

        # Verify on bare remote
        show_res = subprocess.run(
            ["git", "--git-dir", str(remote), "show", "main:10-daily/2026-08-15.md"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Logged entry for sync test" in show_res.stdout
