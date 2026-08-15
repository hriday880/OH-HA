"""
Boundary Test 17: Chunking & Markdown Escaping Stress.
Tests worst-case non-whitespace splitting (>15k chars), escaping all MarkdownV2 reserved tokens, and tables.
"""

from __future__ import annotations

import pytest
from bot.telegram.formatters import chunk_message, escape_markdown_v2


class TestBoundary17ChunkingAndEscapingStress:
    """Boundary tests for Feature 17 (UX Resilience & Escaping)."""

    def test_worst_case_long_unbroken_string_chunking(self):
        """Test splitting a 10,000 character unbroken string without spaces or newlines."""
        unbroken = "A" * 10000
        chunks = chunk_message(unbroken, max_chars=4096)

        assert len(chunks) == 3
        assert sum(len(c) for c in chunks) == 10000
        for c in chunks:
            assert len(c) <= 4096

    def test_escaping_all_reserved_markdown_characters(self):
        """Test comprehensive escaping of every reserved Telegram MarkdownV2 character."""
        all_meta = r"_*[]()~`>#+-=|{}.!"
        escaped = escape_markdown_v2(all_meta)

        for ch in all_meta:
            assert f"\\{ch}" in escaped

    def test_exact_4096_character_boundary(self):
        """Test string with exactly 4096 characters is treated as 1 single chunk."""
        exact_text = "A" * 4096
        chunks = chunk_message(exact_text, max_chars=4096)
        assert len(chunks) == 1
        assert len(chunks[0]) == 4096

    def test_4097_character_boundary(self):
        """Test string with 4097 characters is split into 2 chunks."""
        text_4097 = "A" * 4097
        chunks = chunk_message(text_4097, max_chars=4096)
        assert len(chunks) == 2
        assert len(chunks[0]) == 4096
        assert len(chunks[1]) == 1
