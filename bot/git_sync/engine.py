"""
Remote Git Synchronization Engine.

Provides complete Git repository lifecycle management:
- Initial clone / init with credential injection
- Bidirectional pull and rebase with automated stash protection
- Debounced commit and push queue for batched note writes
- Exponential backoff retry logic for cloud container network resilience
- Non-destructive conflict handling integration
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Union

from bot.git_sync.auth import GitAuthManager, scrub_git_credentials
from bot.git_sync.conflict import ConflictResolver

logger = logging.getLogger(__name__)


@dataclass
class SyncStatus:
    """Represents the current Git synchronization state of the Obsidian vault."""

    is_synced: bool
    last_sync_time: Optional[datetime] = None
    uncommitted_changes: int = 0
    unpushed_commits: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_synced": self.is_synced,
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "uncommitted_changes": self.uncommitted_changes,
            "unpushed_commits": self.unpushed_commits,
            "error": self.error,
        }


class DebouncedPushQueue:
    """
    Asynchronous debounced push coalescer.
    Batches rapid successive file mutations within a configurable window into a single Git commit/push operation.
    """

    def __init__(
        self,
        debounce_seconds: float = 2.0,
        push_callback: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.debounce_seconds = float(debounce_seconds)
        self.push_callback = push_callback
        self.queue: List[str] = []
        self._timer_task: Optional[asyncio.Task[None]] = None
        self.push_count: int = 0
        self.lock = asyncio.Lock()

    async def enqueue(self, file_path: str) -> None:
        """
        Add a modified note path to the sync queue and reset the debounce countdown timer.
        """
        async with self.lock:
            self.queue.append(file_path)
            if self._timer_task and not self._timer_task.done():
                self._timer_task.cancel()
            self._timer_task = asyncio.create_task(self._debounce_worker())

    async def _debounce_worker(self) -> None:
        """Internal worker task waiting for the debounce interval to elapse."""
        try:
            await asyncio.sleep(self.debounce_seconds)
            await self.flush()
        except asyncio.CancelledError:
            pass

    async def flush(self) -> int:
        """
        Immediately drain all queued file mutations and invoke the push callback.
        Returns the number of flushed file paths.
        """
        async with self.lock:
            if not self.queue:
                return 0

            count = len(self.queue)
            self.queue.clear()
            self.push_count += 1

            if self.push_callback:
                try:
                    if inspect.iscoroutinefunction(self.push_callback):
                        await self.push_callback(count)
                    else:
                        res = self.push_callback(count)
                        if inspect.isawaitable(res):
                            await res
                except Exception as e:
                    logger.error(f"Error in DebouncedPushQueue callback: {e}")

            return count

    async def stop(self) -> int:
        """Cancel pending debounce timer and flush remaining queue."""
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        return await self.flush()


class GitSyncEngine:
    """
    Comprehensive Git Remote Synchronization Engine for Obsidian Vaults.
    """

    def __init__(
        self,
        repo_path: Union[str, Path],
        remote_url: Optional[str] = None,
        branch: str = "main",
        auth_token: Optional[str] = None,
        ssh_key: Optional[str] = None,
        author_name: str = "OpenHuman Hermes Bot",
        author_email: str = "bot@openhuman.local",
        debounce_seconds: float = 2.0,
        auto_sync_interval: int = 0,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.remote_url = remote_url
        self.branch = branch
        self.auto_sync_interval = auto_sync_interval

        self.auth_manager = GitAuthManager(
            auth_token=auth_token,
            ssh_key=ssh_key,
            author_name=author_name,
            author_email=author_email,
        )
        self.conflict_resolver = ConflictResolver(
            repo_path=self.repo_path,
            remote_name="origin",
            branch=self.branch,
        )
        self.debounce_queue = DebouncedPushQueue(
            debounce_seconds=debounce_seconds,
            push_callback=self._on_debounced_push,
        )

        self.last_sync: Optional[datetime] = None
        self._sync_task: Optional[asyncio.Task[None]] = None
        self._last_error: Optional[str] = None
        self._async_lock = asyncio.Lock()

    def _get_env(self) -> Dict[str, str]:
        """Get subprocess environment dictionary with git identities and ssh commands."""
        return self.auth_manager.get_git_env()

    def _run_git(
        self,
        *args: str,
        check: bool = False,
        timeout: Optional[float] = 30.0,
    ) -> subprocess.CompletedProcess[str]:
        """
        Execute a git subprocess with security environment, error scrubbing, and timeout.
        """
        cmd = ["git", "-C", str(self.repo_path), *args]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=self._get_env(),
                timeout=timeout,
            )
            if check and res.returncode != 0:
                scrubbed_err = scrub_git_credentials(res.stderr.strip() or res.stdout.strip())
                self._last_error = scrubbed_err
                logger.error(f"Git command failed: {' '.join(args)} - {scrubbed_err}")
                raise subprocess.CalledProcessError(res.returncode, cmd, output=res.stdout, stderr=scrubbed_err)
            return res
        except subprocess.TimeoutExpired as te:
            err_msg = f"Git command timed out after {timeout}s: {' '.join(args)}"
            logger.error(err_msg)
            self._last_error = err_msg
            return subprocess.CompletedProcess(cmd, returncode=124, stdout="", stderr=err_msg)

    def initialize_repo(self) -> bool:
        """
        Initialize or clone the Git repository into `repo_path`.
        Configures local user.name and user.email.
        """
        self.repo_path.mkdir(parents=True, exist_ok=True)
        git_dir = self.repo_path / ".git"

        if not git_dir.exists():
            if self.remote_url:
                formatted_url = self.auth_manager.format_authenticated_url(self.remote_url)
                logger.info(f"Cloning remote vault repository into {self.repo_path}...")
                clone_res = subprocess.run(
                    ["git", "clone", "-b", self.branch, formatted_url, str(self.repo_path)],
                    capture_output=True,
                    text=True,
                    env=self._get_env(),
                )
                if clone_res.returncode != 0:
                    # Fallback clone without branch specification (e.g. for empty or default repos)
                    clone_res = subprocess.run(
                        ["git", "clone", formatted_url, str(self.repo_path)],
                        capture_output=True,
                        text=True,
                        env=self._get_env(),
                    )
                if clone_res.returncode != 0:
                    logger.warning(
                        f"Clone failed ({scrub_git_credentials(clone_res.stderr.strip())}). Initializing local repository."
                    )
                    self._run_git("init", "-b", self.branch)
                    self._run_git("remote", "add", "origin", formatted_url)
            else:
                self._run_git("init", "-b", self.branch)

        # Set user config locally
        self._run_git("config", "user.name", self.auth_manager.author_name)
        self._run_git("config", "user.email", self.auth_manager.author_email)
        return True

    def has_uncommitted_changes(self) -> bool:
        """Check if repository contains modified, staged, or untracked changes."""
        res = self._run_git("status", "--porcelain")
        return bool(res.stdout.strip())

    def get_uncommitted_count(self) -> int:
        """Return the count of uncommitted and untracked files."""
        res = self._run_git("status", "--porcelain")
        lines = [line for line in res.stdout.strip().splitlines() if line.strip()]
        return len(lines)

    def get_unpushed_count(self) -> int:
        """Return the count of unpushed local commits against origin."""
        res = self._run_git("rev-list", "--count", f"origin/{self.branch}..HEAD")
        if res.returncode == 0 and res.stdout.strip().isdigit():
            return int(res.stdout.strip())
        return 0

    def pull_and_rebase(self) -> bool:
        """
        Pull upstream remote changes and rebase local commits with auto-stash safety:
        1. Checks for uncommitted modifications.
        2. Stashes dirty state if present.
        3. Pulls remote changes with rebase.
        4. Restores dirty state via stash pop.
        5. Updates last_sync timestamp on success.
        """
        dirty = self.has_uncommitted_changes()
        stash_created = False

        if dirty:
            stash_res = self._run_git("stash", "save", "-u", "auto-stash-before-pull")
            if stash_res.returncode == 0 and "No local changes" not in stash_res.stdout:
                stash_created = True

        res = self._run_git("pull", "--rebase", "origin", self.branch)

        if stash_created:
            pop_res = self._run_git("stash", "pop")
            if pop_res.returncode != 0:
                logger.warning(
                    f"Auto-stash pop reported conflicts or warnings: {scrub_git_credentials(pop_res.stderr)}"
                )

        if res.returncode == 0:
            self.last_sync = datetime.now(timezone.utc)
            self._last_error = None
            return True
        else:
            self._last_error = scrub_git_credentials(res.stderr.strip() or res.stdout.strip())
            logger.error(f"Git pull and rebase failed: {self._last_error}")
            return False

    def commit_and_push(
        self,
        commit_message: Optional[str] = None,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
    ) -> bool:
        """
        Stage all modifications, create a Git commit, and push to remote.
        Includes retry and exponential backoff for transient cloud network failures.
        """
        msg = commit_message or "Agent auto-sync update"

        # Stage all changes
        self._run_git("add", ".")

        # Check if there are staged changes to commit
        status_res = self._run_git("status", "--porcelain")
        has_staged = False
        for line in status_res.stdout.splitlines():
            if line and line[0] in ("M", "A", "D", "R", "C"):
                has_staged = True
                break

        if has_staged:
            commit_res = self._run_git("commit", "-m", msg)
            if commit_res.returncode != 0:
                logger.warning(f"Git commit returned code {commit_res.returncode}: {commit_res.stderr}")

        # Attempt push with retry loop
        for attempt in range(max_retries):
            push_res = self._run_git("push", "origin", self.branch)
            if push_res.returncode == 0:
                self.last_sync = datetime.now(timezone.utc)
                self._last_error = None
                return True

            # If push failed because remote was updated, attempt pull/rebase and retry
            logger.warning(
                f"Git push attempt {attempt + 1}/{max_retries} failed: "
                f"{scrub_git_credentials(push_res.stderr.strip())}. Retrying..."
            )
            self.pull_and_rebase()
            time.sleep(retry_backoff * (2**attempt))

        self._last_error = scrub_git_credentials(push_res.stderr.strip() or "Max push retries exceeded")
        return False

    async def _on_debounced_push(self, count: int) -> None:
        """Handler called by DebouncedPushQueue when debounce window expires."""
        async with self._async_lock:
            msg = f"Agent batched sync ({count} modifications)"
            # Execute commit and push in executor thread to avoid blocking event loop
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.commit_and_push, msg)

    async def sync_now(self) -> SyncStatus:
        """
        Run an immediate bidirectional sync (flush debounced queue, pull & rebase, commit & push).
        Returns the updated SyncStatus.
        """
        async with self._async_lock:
            # Drain any pending debounced writes
            await self.debounce_queue.flush()

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.pull_and_rebase)
            if self.has_uncommitted_changes() or self.get_unpushed_count() > 0:
                await loop.run_in_executor(None, self.commit_and_push, "Manual sync trigger")

            return self.get_status()

    def get_status(self) -> SyncStatus:
        """
        Inspect current Git repository status.
        """
        uncommitted = self.get_uncommitted_count()
        unpushed = self.get_unpushed_count()
        is_clean = (uncommitted == 0 and unpushed == 0)

        return SyncStatus(
            is_synced=is_clean,
            last_sync_time=self.last_sync,
            uncommitted_changes=uncommitted,
            unpushed_commits=unpushed,
            error=self._last_error,
        )

    def start_background_sync(self) -> None:
        """Start periodic background sync loop if auto_sync_interval > 0."""
        if self.auto_sync_interval > 0 and self._sync_task is None:
            self._sync_task = asyncio.create_task(self._background_sync_loop())

    def stop_background_sync(self) -> None:
        """Cancel periodic background sync loop."""
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            self._sync_task = None

    async def _background_sync_loop(self) -> None:
        """Continuous background sync worker."""
        while True:
            try:
                await asyncio.sleep(self.auto_sync_interval)
                await self.sync_now()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background sync loop: {e}")
