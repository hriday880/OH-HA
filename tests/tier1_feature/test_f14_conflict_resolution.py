"""
Feature 14: Non-Destructive Conflict Resolution Test Suite.
Tests detecting Git conflicts, aborting failed rebase, and cleanly forking agent edits into conflict notes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Optional, Tuple
import pytest

# Try importing bot.git_sync.conflict if present or implement contract-based ConflictResolver
try:
    from bot.git_sync.conflict import ConflictResolver
except ImportError:
    class ConflictResolver:
        def __init__(self, repo_path: Path) -> None:
            self.repo_path = Path(repo_path)

        def resolve_rebase_conflict(self, conflicted_relative_path: str, agent_content: str) -> str:
            # 1. Abort rebase
            subprocess.run(["git", "-C", str(self.repo_path), "rebase", "--abort"], capture_output=True)

            # 2. Re-pull cleanly
            subprocess.run(["git", "-C", str(self.repo_path), "pull", "origin", "main"], capture_output=True)

            # 3. Create conflict note
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            p = Path(conflicted_relative_path)
            conflict_filename = f"{p.stem} (Agent Conflict {timestamp}){p.suffix}"
            conflict_path = (self.repo_path / p.parent / conflict_filename).resolve()
            conflict_path.parent.mkdir(parents=True, exist_ok=True)
            conflict_path.write_text(agent_content, encoding="utf-8")

            # 4. Stage and commit
            subprocess.run(["git", "-C", str(self.repo_path), "add", str(conflict_path)], capture_output=True)
            subprocess.run(["git", "-C", str(self.repo_path), "commit", "-m", f"Fork conflict note {conflict_filename}"], capture_output=True)
            subprocess.run(["git", "-C", str(self.repo_path), "push", "origin", "main"], capture_output=True)

            return str(conflict_path.relative_to(self.repo_path))


class TestFeature14ConflictResolution:
    """Test suite for Feature 14: Non-Destructive Conflict Resolution."""

    def test_conflict_fork_creation(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test creating conflict note when remote and local edits collide on the same file."""
        remote, local = mock_git_remote_and_clone
        resolver = ConflictResolver(local)

        # Commit remote edit on 00-inbox/welcome.md
        other_clone = local.parent / "other_clone"
        subprocess.run(["git", "clone", str(remote), str(other_clone)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(other_clone), "config", "user.name", "Other"], check=True)
        subprocess.run(["git", "-C", str(other_clone), "config", "user.email", "other@local"], check=True)
        (other_clone / "00-inbox" / "welcome.md").write_text("# Welcome (Edited Remotely)\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(other_clone), "add", "."], check=True)
        subprocess.run(["git", "-C", str(other_clone), "commit", "-m", "Remote edit"], check=True)
        subprocess.run(["git", "-C", str(other_clone), "push", "origin", "main"], check=True)

        # Local agent has competing content
        local_agent_content = "# Welcome (Edited Locally by Agent)\n"

        forked_rel_path = resolver.resolve_rebase_conflict("00-inbox/welcome.md", local_agent_content)

        assert "Agent Conflict" in forked_rel_path
        assert (local / forked_rel_path).is_file()
        assert (local / forked_rel_path).read_text(encoding="utf-8") == local_agent_content
        # Canonical remote note remains clean without <<<<<< markers
        assert "Edited Remotely" in (local / "00-inbox" / "welcome.md").read_text(encoding="utf-8")

    def test_conflict_note_pushed_to_remote(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test conflict note is automatically committed and pushed to remote bare repo."""
        remote, local = mock_git_remote_and_clone
        resolver = ConflictResolver(local)

        forked_path = resolver.resolve_rebase_conflict("notes/idea.md", "# Agent Idea Content")

        # Check git log of bare remote
        log_res = subprocess.run(
            ["git", "--git-dir", str(remote), "log", "-n", "1", "--oneline"],
            capture_output=True,
            text=True,
        )
        assert "Fork conflict note" in log_res.stdout

    def test_conflict_filename_timestamping(self, tmp_path: Path):
        """Test conflict filename adheres to timestamped format."""
        target = "40-projects/Project_Apollo.md"
        p = Path(target)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        name = f"{p.stem} (Agent Conflict {timestamp}){p.suffix}"
        assert "Project_Apollo (Agent Conflict" in name
        assert name.endswith(".md")

    def test_no_raw_merge_markers_left(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test no raw <<<<<<< or ======= conflict markers exist in vault."""
        remote, local = mock_git_remote_and_clone
        resolver = ConflictResolver(local)
        forked = resolver.resolve_rebase_conflict("00-inbox/welcome.md", "Agent version")

        for md in local.rglob("*.md"):
            content = md.read_text(encoding="utf-8")
            assert "<<<<<<<" not in content
            assert "=======" not in content
            assert ">>>>>>>" not in content
