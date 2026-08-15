"""
Non-Destructive Git Conflict Resolution Engine.

Ensures zero data loss when local agent notes collide with upstream remote changes.
Preserves the canonical remote note cleanly and forks competing agent edits into
a distinct `<Note> (Agent Conflict <timestamp>).md` note, automatically staged,
committed, and pushed to remote.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import subprocess
from typing import Optional, Union

from bot.git_sync.auth import scrub_git_credentials

logger = logging.getLogger(__name__)


class ConflictResolver:
    """
    Handles non-destructive conflict recovery during Git pull/rebase operations.
    """

    def __init__(
        self,
        repo_path: Union[str, Path],
        remote_name: str = "origin",
        branch: str = "main",
        env: Optional[dict[str, str]] = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.remote_name = remote_name
        self.branch = branch
        self.env = env

    def _run_git(
        self,
        *args: str,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Execute a git command within the repository."""
        cmd = ["git", "-C", str(self.repo_path), *args]
        env = self.env.copy() if self.env else os.environ.copy()
        env["GIT_CONFIG_GLOBAL"] = "/dev/null"
        env["GIT_CONFIG_SYSTEM"] = "/dev/null"
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
        )
        if check and res.returncode != 0:
            scrubbed_err = scrub_git_credentials(res.stderr.strip())
            logger.error(f"Git command failed: {' '.join(args)} - {scrubbed_err}")
            raise subprocess.CalledProcessError(res.returncode, cmd, output=res.stdout, stderr=scrubbed_err)
        return res

    def is_in_conflict_state(self) -> bool:
        """Check if repository is currently in a merge or rebase conflict state."""
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            return False

        if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
            return True
        if (git_dir / "MERGE_HEAD").exists() or (git_dir / "CHERRY_PICK_HEAD").exists():
            return True

        status_res = self._run_git("status", "--porcelain")
        for line in status_res.stdout.splitlines():
            # 'UU', 'AA', 'UD', 'DU' indicate unmerged conflict states
            if line.startswith(("UU ", "AA ", "UD ", "DU ", "DD ", "AU ", "UA ")):
                return True
        return False

    def abort_conflict_state(self) -> bool:
        """Safely abort any pending rebase or merge in progress."""
        git_dir = self.repo_path / ".git"
        aborted = False

        if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
            res = self._run_git("rebase", "--abort")
            aborted = (res.returncode == 0)

        if (git_dir / "MERGE_HEAD").exists():
            res = self._run_git("merge", "--abort")
            aborted = (res.returncode == 0)

        return aborted

    def generate_conflict_filename(
        self,
        conflicted_relative_path: str,
        timestamp_str: Optional[str] = None,
    ) -> tuple[str, Path]:
        """
        Generate standard timestamped conflict filename and absolute destination path.

        Format: `<NoteStem> (Agent Conflict <timestamp>).md`
        """
        if not timestamp_str:
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

        p = Path(conflicted_relative_path)
        stem = p.stem
        suffix = p.suffix or ".md"

        conflict_filename = f"{stem} (Agent Conflict {timestamp_str}){suffix}"
        target_path = (self.repo_path / p.parent / conflict_filename).resolve()

        rel_path = str(target_path.relative_to(self.repo_path)).replace("\\", "/")
        return rel_path, target_path

    def resolve_rebase_conflict(
        self,
        conflicted_relative_path: str,
        agent_content: str,
        commit_message: Optional[str] = None,
    ) -> str:
        """
        Resolve a collision non-destructively:
        1. Aborts in-progress rebase/merge to restore pre-rebase branch state.
        2. Pulls remote branch cleanly to accept canonical remote updates.
        3. Creates a new timestamped conflict note containing the local agent modifications.
        4. Stages, commits, and pushes the conflict note to remote repository.
        5. Returns the relative path to the newly created conflict note.
        """
        logger.warning(
            f"Resolving collision on note '{conflicted_relative_path}'. Preserving remote note and forking agent version."
        )

        # 1. Abort rebase/merge if in progress
        self.abort_conflict_state()

        # 2. Fetch and reset working tree to match clean canonical remote state
        self._run_git("fetch", self.remote_name, self.branch)
        self._run_git("reset", "--hard", f"{self.remote_name}/{self.branch}")

        # 3. Create the timestamped conflict note
        rel_conflict_path, abs_conflict_path = self.generate_conflict_filename(conflicted_relative_path)
        abs_conflict_path.parent.mkdir(parents=True, exist_ok=True)
        abs_conflict_path.write_text(agent_content, encoding="utf-8")

        # 4. Stage conflict note
        self._run_git("add", str(abs_conflict_path))

        # 5. Commit conflict note
        msg = commit_message or f"Fork conflict note {abs_conflict_path.name}"
        self._run_git("commit", "-m", msg)

        # 6. Push conflict note to remote
        self._run_git("push", self.remote_name, self.branch)

        logger.info(f"Non-destructive conflict note saved to '{rel_conflict_path}' and pushed to remote.")
        return rel_conflict_path
