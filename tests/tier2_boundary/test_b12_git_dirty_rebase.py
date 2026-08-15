"""
Boundary Test 12: Dirty Working Tree & Git Pull Rebase.
Tests auto-stashing multiple dirty files, untracked files coexistence, and stash pop integrity.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import pytest
from bot.git_sync.engine import GitSyncEngine


class TestBoundary12GitDirtyRebase:
    """Boundary tests for Feature 12 (Git Pull/Rebase)."""

    def test_pull_with_multiple_dirty_files(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test stashing and restoring multiple modified files during pull."""
        remote, local = mock_git_remote_and_clone
        engine = GitSyncEngine(repo_path=local, branch="main")

        # Create multiple local dirty files
        (local / "dirty1.md").write_text("# Dirty 1\n", encoding="utf-8")
        (local / "dirty2.md").write_text("# Dirty 2\n", encoding="utf-8")

        # Push a commit to remote from elsewhere
        other_clone = local.parent / "other_clone"
        subprocess.run(["git", "clone", str(remote), str(other_clone)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(other_clone), "config", "user.name", "Other"], check=True)
        subprocess.run(["git", "-C", str(other_clone), "config", "user.email", "other@local"], check=True)
        (other_clone / "remote_update.md").write_text("# Remote Content\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(other_clone), "add", "."], check=True)
        subprocess.run(["git", "-C", str(other_clone), "commit", "-m", "Remote update"], check=True)
        subprocess.run(["git", "-C", str(other_clone), "push", "origin", "main"], check=True)

        success = engine.pull_and_rebase()
        assert success is True
        assert (local / "remote_update.md").is_file()
        assert (local / "dirty1.md").is_file()
        assert (local / "dirty2.md").is_file()

    def test_untracked_files_preserved_during_sync(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test newly added untracked files are not wiped during pull operations."""
        remote, local = mock_git_remote_and_clone
        engine = GitSyncEngine(repo_path=local, branch="main")

        (local / "untracked_scratch.txt").write_text("scratchpad content", encoding="utf-8")
        engine.pull_and_rebase()

        assert (local / "untracked_scratch.txt").is_file()
        assert (local / "untracked_scratch.txt").read_text() == "scratchpad content"

    def test_has_uncommitted_changes_accuracy(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test accuracy of uncommitted changes detector."""
        remote, local = mock_git_remote_and_clone
        engine = GitSyncEngine(repo_path=local, branch="main")

        assert engine.has_uncommitted_changes() is False

        (local / "mod.md").write_text("mod", encoding="utf-8")
        assert engine.has_uncommitted_changes() is True
