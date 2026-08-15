"""
Acceptance Criterion 4 (AC 4) Test Suite.
Verifies: "An automated test or script demonstrates that the system can pull updates from and push changes to a remote repository (representing the remote Obsidian vault)."
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import pytest
from bot.git_sync.engine import GitSyncEngine
from bot.vault.manager import VaultManager


class TestAC4RemoteGitSync:
    """Acceptance Criterion 4: Bidirectional Remote Git Synchronization Simulation."""

    def test_ac4_remote_git_sync_simulation(self, bare_git_remote: Path, tmp_path: Path):
        """
        [AC 4 Core Test]
        Demonstrates that the agent system can clone, pull updates from, and push local note
        mutations to a remote Git repository representing the user's remote Obsidian vault.
        """
        # 1. Clone agent working directory from bare remote
        agent_vault = tmp_path / "agent_vault"
        subprocess.run(["git", "clone", str(bare_git_remote), str(agent_vault)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(agent_vault), "config", "user.name", "Cloud Agent"], check=True)
        subprocess.run(["git", "-C", str(agent_vault), "config", "user.email", "agent@openhuman.local"], check=True)

        vault = VaultManager(agent_vault)
        sync_engine = GitSyncEngine(repo_path=agent_vault, branch="main")

        # 2. Simulate User pushing an update to remote from their Desktop Obsidian
        desktop_vault = tmp_path / "desktop_vault"
        subprocess.run(["git", "clone", str(bare_git_remote), str(desktop_vault)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(desktop_vault), "config", "user.name", "User Desktop"], check=True)
        subprocess.run(["git", "-C", str(desktop_vault), "config", "user.email", "user@desktop.local"], check=True)

        (desktop_vault / "00-inbox").mkdir(exist_ok=True)
        (desktop_vault / "00-inbox" / "desktop_quick_note.md").write_text(
            "---\ntitle: Desktop Quick Note\n---\n# Desktop Note\nCreated on desktop Obsidian.\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(desktop_vault), "add", "."], check=True)
        subprocess.run(["git", "-C", str(desktop_vault), "commit", "-m", "User created note on desktop"], check=True)
        subprocess.run(["git", "-C", str(desktop_vault), "push", "origin", "main"], check=True)

        # 3. Agent pulls updates from remote repository
        pulled = sync_engine.pull_and_rebase()
        assert pulled is True
        assert (agent_vault / "00-inbox" / "desktop_quick_note.md").is_file()

        # 4. Agent writes a new note locally
        agent_note = vault.write_note(
            "50-knowledge/Agent_Generated_Synthesis.md",
            "# Agent Synthesis\n\nSynthesized knowledge after analyzing desktop notes.",
            mode="overwrite",
            metadata={"title": "Agent Synthesis", "tags": ["agent", "synthesis"]},
        )
        assert (agent_vault / "50-knowledge" / "Agent_Generated_Synthesis.md").is_file()

        # 5. Agent commits and pushes changes back to remote repository
        pushed = sync_engine.commit_and_push(commit_message="Agent synced new synthesis note")
        assert pushed is True

        # 6. Verify remote bare repository reflects both commits and files
        remote_log = subprocess.run(
            ["git", "--git-dir", str(bare_git_remote), "log", "-n", "3", "--oneline"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "User created note on desktop" in remote_log.stdout
        assert "Agent synced new synthesis note" in remote_log.stdout

        # Verify remote content via git show
        remote_file_content = subprocess.run(
            ["git", "--git-dir", str(bare_git_remote), "show", "main:50-knowledge/Agent_Generated_Synthesis.md"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Synthesized knowledge after analyzing desktop notes" in remote_file_content.stdout

    def test_ac4_bidirectional_roundtrip(self, bare_git_remote: Path, tmp_path: Path):
        """Test continuous bidirectional exchange between Desktop and Cloud Agent."""
        agent_dir = tmp_path / "c1"
        user_dir = tmp_path / "c2"

        subprocess.run(["git", "clone", str(bare_git_remote), str(agent_dir)], check=True, capture_output=True)
        subprocess.run(["git", "clone", str(bare_git_remote), str(user_dir)], check=True, capture_output=True)

        for d, name in [(agent_dir, "Agent"), (user_dir, "User")]:
            subprocess.run(["git", "-C", str(d), "config", "user.name", name], check=True)
            subprocess.run(["git", "-C", str(d), "config", "user.email", f"{name.lower()}@local"], check=True)

        engine_agent = GitSyncEngine(agent_dir, branch="main")
        engine_user = GitSyncEngine(user_dir, branch="main")

        # Agent writes note 1
        (agent_dir / "note1.md").write_text("from agent", encoding="utf-8")
        assert engine_agent.commit_and_push("agent note 1") is True

        # User pulls note 1 and writes note 2
        assert engine_user.pull_and_rebase() is True
        assert (user_dir / "note1.md").is_file()
        (user_dir / "note2.md").write_text("from user", encoding="utf-8")
        assert engine_user.commit_and_push("user note 2") is True

        # Agent pulls note 2
        assert engine_agent.pull_and_rebase() is True
        assert (agent_dir / "note2.md").is_file()
