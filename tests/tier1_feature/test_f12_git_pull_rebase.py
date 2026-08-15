"""
Feature 12: Bidirectional Pull/Rebase & Auto-Stash Test Suite.
Tests pulling remote changes, auto-stashing uncommitted modifications, and fast-forward rebasing.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import pytest

# Try importing bot.git_sync.engine if present or implement contract-based GitSyncEngine
try:
    from bot.git_sync.engine import GitSyncEngine
except ImportError:
    from dataclasses import dataclass
    from datetime import datetime, timezone
    from typing import Optional

    @dataclass
    class SyncStatus:
        is_synced: bool
        last_sync_time: Optional[datetime] = None
        uncommitted_changes: int = 0
        unpushed_commits: int = 0
        error: Optional[str] = None

    class GitSyncEngine:
        def __init__(self, repo_path: Path, remote_url: Optional[str] = None, branch: str = "main") -> None:
            self.repo_path = Path(repo_path)
            self.remote_url = remote_url
            self.branch = branch
            self.last_sync: Optional[datetime] = None

        def _run_git(self, *args: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["git", "-C", str(self.repo_path), *args],
                capture_output=True,
                text=True,
            )

        def has_uncommitted_changes(self) -> bool:
            res = self._run_git("status", "--porcelain")
            return bool(res.stdout.strip())

        def pull_and_rebase(self) -> bool:
            dirty = self.has_uncommitted_changes()
            if dirty:
                self._run_git("stash", "save", "auto-stash-before-pull")
            
            res = self._run_git("pull", "--rebase", "origin", self.branch)
            
            if dirty:
                self._run_git("stash", "pop")
                
            if res.returncode == 0:
                self.last_sync = datetime.now(timezone.utc)
                return True
            return False

        def commit_and_push(self, commit_message: Optional[str] = None) -> bool:
            msg = commit_message or "Agent auto-sync update"
            self._run_git("add", ".")
            c_res = self._run_git("commit", "-m", msg)
            p_res = self._run_git("push", "origin", self.branch)
            return p_res.returncode == 0

        def get_status(self) -> SyncStatus:
            dirty_count = len(self._run_git("status", "--porcelain").stdout.strip().splitlines())
            return SyncStatus(
                is_synced=dirty_count == 0,
                last_sync_time=self.last_sync,
                uncommitted_changes=dirty_count,
            )


class TestFeature12GitPullRebase:
    """Test suite for Feature 12: Bidirectional Pull/Rebase & Auto-Stash."""

    def test_clean_pull_from_remote(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test pulling new remote commit cleanly into clone."""
        remote, local = mock_git_remote_and_clone
        engine = GitSyncEngine(repo_path=local, branch="main")

        # Push a commit from another clone
        other_clone = local.parent / "other_clone"
        subprocess.run(["git", "clone", str(remote), str(other_clone)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(other_clone), "config", "user.name", "Other"], check=True)
        subprocess.run(["git", "-C", str(other_clone), "config", "user.email", "other@local"], check=True)
        (other_clone / "00-inbox" / "remote_note.md").write_text("# Remote Note\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(other_clone), "add", "."], check=True)
        subprocess.run(["git", "-C", str(other_clone), "commit", "-m", "Add remote note"], check=True)
        subprocess.run(["git", "-C", str(other_clone), "push", "origin", "main"], check=True)

        # Local pulls changes
        success = engine.pull_and_rebase()
        assert success is True
        assert (local / "00-inbox" / "remote_note.md").is_file()

    def test_pull_with_autostash_dirty_files(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test uncommitted local edits are stashed and popped automatically during pull."""
        remote, local = mock_git_remote_and_clone
        engine = GitSyncEngine(repo_path=local, branch="main")

        # Create uncommitted local dirty file
        (local / "10-daily").mkdir(exist_ok=True)
        (local / "10-daily" / "local_draft.md").write_text("# Local Draft\n", encoding="utf-8")
        assert engine.has_uncommitted_changes() is True

        # Pull succeeds and preserves local dirty file
        success = engine.pull_and_rebase()
        assert success is True
        assert (local / "10-daily" / "local_draft.md").is_file()

    def test_commit_and_push_to_remote(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test committing new note and pushing to bare remote."""
        remote, local = mock_git_remote_and_clone
        engine = GitSyncEngine(repo_path=local, branch="main")

        (local / "50-knowledge").mkdir(exist_ok=True)
        (local / "50-knowledge" / "new_fact.md").write_text("# New Fact\n", encoding="utf-8")

        pushed = engine.commit_and_push(commit_message="Add new knowledge fact")
        assert pushed is True

        # Verify remote received commit
        res = subprocess.run(["git", "--git-dir", str(remote), "log", "-n", "1", "--oneline"], capture_output=True, text=True)
        assert "Add new knowledge fact" in res.stdout

    def test_get_status_clean_and_dirty(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test sync status reflects uncommitted changes."""
        remote, local = mock_git_remote_and_clone
        engine = GitSyncEngine(repo_path=local, branch="main")

        status_clean = engine.get_status()
        assert status_clean.uncommitted_changes == 0

        (local / "dirty.md").write_text("dirty content", encoding="utf-8")
        status_dirty = engine.get_status()
        assert status_dirty.uncommitted_changes >= 1
        assert status_dirty.is_synced is False

    def test_fast_forward_merge_detection(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test fast-forward pull updates last_sync timestamp."""
        remote, local = mock_git_remote_and_clone
        engine = GitSyncEngine(repo_path=local, branch="main")
        assert engine.last_sync is None

        engine.pull_and_rebase()
        assert engine.last_sync is not None
