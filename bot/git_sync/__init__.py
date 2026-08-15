"""
Git Synchronization Engine Package.

Provides remote Git repository lifecycle management, credential protection,
bidirectional pull/rebase with auto-stash, debounced commit queue,
and non-destructive conflict note forking.
"""

from __future__ import annotations

from bot.git_sync.auth import GitAuthManager, scrub_git_credentials
from bot.git_sync.conflict import ConflictResolver
from bot.git_sync.engine import DebouncedPushQueue, GitSyncEngine, SyncStatus

__all__ = [
    "GitAuthManager",
    "scrub_git_credentials",
    "ConflictResolver",
    "DebouncedPushQueue",
    "GitSyncEngine",
    "SyncStatus",
]
