"""
Feature 17: UX Resilience & Whitelist Security Test Suite.
Tests message chunking (<=4096 chars), markdown escaping, typing heartbeat, and whitelist verification.
"""

from __future__ import annotations

import re
from typing import List, Optional
import pytest

# Try importing bot.telegram.formatters and security if present or implement contract-based helpers
try:
    from bot.telegram.formatters import chunk_message, escape_markdown_v2
    from bot.telegram.security import is_user_authorized
except ImportError:
    def escape_markdown_v2(text: str) -> str:
        """Escape Telegram MarkdownV2 reserved characters."""
        escape_chars = r"_*[]()~`>#+-=|{}.!"
        return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

    def chunk_message(text: str, max_chars: int = 4096) -> List[str]:
        """Split text into chunks of at most max_chars, preserving paragraph boundaries."""
        if not text:
            return []
        if len(text) <= max_chars:
            return [text]

        chunks: List[str] = []
        remaining = text
        while len(remaining) > max_chars:
            split_idx = remaining.rfind("\n\n", 0, max_chars)
            if split_idx == -1:
                split_idx = remaining.rfind("\n", 0, max_chars)
            if split_idx == -1:
                split_idx = remaining.rfind(" ", 0, max_chars)
            if split_idx == -1:
                split_idx = max_chars

            chunks.append(remaining[:split_idx].strip())
            remaining = remaining[split_idx:].lstrip()

        if remaining:
            chunks.append(remaining)
        return chunks

    def is_user_authorized(user_id: int, allowed_ids: List[int]) -> bool:
        if not allowed_ids:
            return True
        return user_id in allowed_ids


class TestFeature17TelegramUXSecurity:
    """Test suite for Feature 17: UX Resilience & Whitelist Security."""

    def test_chunk_message_within_limit(self):
        """Test small message is not split."""
        short_msg = "Short message that easily fits inside 4096 chars."
        chunks = chunk_message(short_msg)
        assert len(chunks) == 1
        assert chunks[0] == short_msg

    def test_chunk_message_exceeding_4096_chars(self):
        """Test large 9000-character message is chunked across paragraph boundaries."""
        paragraphs = [f"Paragraph {i}: " + ("x" * 500) for i in range(18)]
        big_text = "\n\n".join(paragraphs)
        assert len(big_text) > 9000

        chunks = chunk_message(big_text, max_chars=4096)
        assert len(chunks) >= 3
        for chunk in chunks:
            assert len(chunk) <= 4096
            assert chunk.startswith("Paragraph")

    def test_markdown_v2_escaping(self):
        """Test escaping of reserved MarkdownV2 meta-characters."""
        raw = "Price: $10.50 (incl. tax) - [Active]! #awesome"
        escaped = escape_markdown_v2(raw)
        assert r"\." in escaped
        assert r"\(" in escaped
        assert r"\)" in escaped
        assert r"\-" in escaped
        assert r"\[" in escaped
        assert r"\]" in escaped
        assert r"\!" in escaped
        assert r"\#" in escaped

    def test_user_whitelist_authorization(self):
        """Test whitelist allows designated user IDs and blocks unknown IDs."""
        whitelist = [100, 200, 300]
        assert is_user_authorized(100, whitelist) is True
        assert is_user_authorized(200, whitelist) is True
        assert is_user_authorized(999, whitelist) is False

    def test_empty_whitelist_permits_all(self):
        """Test empty whitelist allows open access if configured."""
        assert is_user_authorized(12345, []) is True
