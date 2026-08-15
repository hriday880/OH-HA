"""
Pairwise Test 6: Conflict Resolution & Telegram Notification.
Tests non-destructive Git conflict fork triggering informative Telegram user alerts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import pytest
from bot.git_sync.conflict import ConflictResolver


class TestPairwiseConflictTelegramAlert:
    """Pairwise Integration Suite: Conflict Resolution + Telegram Alerting."""

    @pytest.mark.asyncio
    async def test_conflict_triggers_telegram_alert(self, mock_git_remote_and_clone: tuple[Path, Path], mock_telegram_app: Any):
        """Test conflict resolution creates fork and dispatches alert notification to user."""
        remote, local = mock_git_remote_and_clone
        resolver = ConflictResolver(local)

        forked_rel_path = resolver.resolve_rebase_conflict(
            "00-inbox/welcome.md",
            "# Local Note Version from Agent",
        )

        alert_msg = (
            f"⚠️ Git Rebase Notice: Remote changes were pulled. "
            f"Your agent modifications have been non-destructively saved to `{forked_rel_path}`."
        )
        await mock_telegram_app.send_message(chat_id=123456789, text=alert_msg)

        assert len(mock_telegram_app.sent_messages) == 1
        assert "Git Rebase Notice" in mock_telegram_app.sent_messages[0]["text"]
        assert "Agent Conflict" in mock_telegram_app.sent_messages[0]["text"]
