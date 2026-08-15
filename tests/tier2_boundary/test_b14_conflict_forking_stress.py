"""
Boundary Test 14: Non-Destructive Conflict Forking Stress.
Tests generating multiple successive conflict notes on the same file without data loss.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import pytest
from bot.git_sync.conflict import ConflictResolver


class TestBoundary14ConflictForkingStress:
    """Boundary tests for Feature 14 (Conflict Resolution)."""

    def test_successive_conflict_notes_uniqueness(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test multiple conflict events generate distinct timestamped conflict notes."""
        remote, local = mock_git_remote_and_clone
        resolver = ConflictResolver(local)

        fork_1 = resolver.resolve_rebase_conflict("notes/idea.md", "Content Version 1")
        # Sleep briefly to ensure distinct timestamp
        import time
        time.sleep(1.1)
        fork_2 = resolver.resolve_rebase_conflict("notes/idea.md", "Content Version 2")

        assert fork_1 != fork_2
        assert (local / fork_1).is_file()
        assert (local / fork_2).is_file()
        assert (local / fork_1).read_text(encoding="utf-8") == "Content Version 1"
        assert (local / fork_2).read_text(encoding="utf-8") == "Content Version 2"

    def test_conflict_note_with_spaces_and_subdirectories(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test resolving conflict in deeply nested paths with spaces."""
        remote, local = mock_git_remote_and_clone
        resolver = ConflictResolver(local)

        nested_path = "40-projects/sub folder/Deep Project.md"
        forked = resolver.resolve_rebase_conflict(nested_path, "# Deep Project Agent Version")

        assert "Deep Project (Agent Conflict" in forked
        assert (local / forked).is_file()

    def test_clean_working_tree_after_conflict_resolution(self, mock_git_remote_and_clone: tuple[Path, Path]):
        """Test working tree is clean (no untracked conflict residues) after resolution."""
        remote, local = mock_git_remote_and_clone
        resolver = ConflictResolver(local)

        resolver.resolve_rebase_conflict("00-inbox/welcome.md", "Agent Welcome")

        import subprocess
        status = subprocess.run(["git", "-C", str(local), "status", "--porcelain"], capture_output=True, text=True)
        assert status.stdout.strip() == ""
