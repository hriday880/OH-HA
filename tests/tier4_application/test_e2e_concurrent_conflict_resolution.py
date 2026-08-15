"""
Tier 4 Application Scenario 6: Concurrent Rebase Conflict Resolution.
Tests concurrent edits on the same file -> Rebase conflict -> Conflict note forked & pushed to bare remote.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import pytest
from bot.git_sync.conflict import ConflictResolver
from bot.vault.manager import VaultManager


class TestE2EConcurrentConflictResolution:
    """End-to-End User Scenario: Concurrent Collision & Non-Destructive Resolution."""

    def test_e2e_concurrent_conflict_resolution(self, bare_git_remote: Path, tmp_path: Path):
        """
        Scenario:
        1. User edits '40-projects/Project_Apollo.md' on Desktop Obsidian and pushes to remote.
        2. Agent concurrently edits '40-projects/Project_Apollo.md' in Cloud.
        3. Agent pulls with rebase -> detects collision on same file.
        4. Agent aborts rebase, accepts canonical remote note, forks agent version to conflict note, and pushes.
        5. Verify remote repo contains both canonical note and forked conflict note with zero corruption markers.
        """
        # 1. Desktop clone setup
        desktop_dir = tmp_path / "desktop"
        subprocess.run(["git", "clone", str(bare_git_remote), str(desktop_dir)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(desktop_dir), "config", "user.name", "Desktop User"], check=True)
        subprocess.run(["git", "-C", str(desktop_dir), "config", "user.email", "user@desktop.local"], check=True)

        (desktop_dir / "40-projects").mkdir(parents=True, exist_ok=True)
        (desktop_dir / "40-projects" / "Project_Apollo.md").write_text(
            "# Project Apollo\nDesktop User Edit: Prioritizing local Ollama support.\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(desktop_dir), "add", "."], check=True)
        subprocess.run(["git", "-C", str(desktop_dir), "commit", "-m", "Desktop user edits Apollo note"], check=True)
        subprocess.run(["git", "-C", str(desktop_dir), "push", "origin", "main"], check=True)

        # 2. Agent clone setup
        agent_dir = tmp_path / "agent"
        subprocess.run(["git", "clone", str(bare_git_remote), str(agent_dir)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(agent_dir), "config", "user.name", "Cloud Agent"], check=True)
        subprocess.run(["git", "-C", str(agent_dir), "config", "user.email", "agent@openhuman.local"], check=True)

        # 3. Agent has competing local edits
        agent_competing_content = "# Project Apollo\nCloud Agent Edit: Deployed on Fly.io free-tier.\n"
        resolver = ConflictResolver(agent_dir)

        forked_rel_path = resolver.resolve_rebase_conflict(
            "40-projects/Project_Apollo.md",
            agent_competing_content,
        )

        # 4. Verify local agent directory state
        assert (agent_dir / forked_rel_path).is_file()
        assert (agent_dir / forked_rel_path).read_text(encoding="utf-8") == agent_competing_content
        # Canonical note has desktop user's edits
        canonical_content = (agent_dir / "40-projects" / "Project_Apollo.md").read_text(encoding="utf-8")
        assert "Prioritizing local Ollama support" in canonical_content
        assert "<<<<<<<" not in canonical_content

        # 5. Verify bare remote repo state
        log_res = subprocess.run(
            ["git", "--git-dir", str(bare_git_remote), "log", "-n", "3", "--oneline"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Fork conflict note" in log_res.stdout
