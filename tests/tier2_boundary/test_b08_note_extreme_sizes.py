"""
Boundary Test 8: Extreme Note Sizes & Unicode Stress.
Tests zero-byte notes, large notes (>200KB), multi-language Unicode (CJK, Arabic, Cyrillic), and emojis.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from bot.vault.manager import VaultManager


class TestBoundary08NoteExtremeSizes:
    """Boundary tests for Feature 8 (Note CRUD)."""

    def test_zero_byte_note_read_and_write(self, tmp_path: Path):
        """Test writing and reading an empty note content."""
        vault = tmp_path / "vault"
        vault.mkdir()
        manager = VaultManager(vault)

        note = manager.write_note("00-inbox/empty.md", "", mode="overwrite")
        assert (vault / "00-inbox" / "empty.md").is_file()

        read_note = manager.read_note("00-inbox/empty.md")
        assert read_note.raw_body == ""

    def test_large_note_200kb_write_and_read(self, tmp_path: Path):
        """Test writing and reading a 200KB note with thousands of lines."""
        vault = tmp_path / "vault"
        vault.mkdir()
        manager = VaultManager(vault)

        large_body = ("Line of markdown content with tokens and text.\n" * 4500)
        assert len(large_body) > 200000

        note = manager.write_note("50-knowledge/Large_Corpus.md", large_body, mode="overwrite")
        assert (vault / "50-knowledge" / "Large_Corpus.md").stat().st_size > 200000

        read_back = manager.read_note("50-knowledge/Large_Corpus.md")
        assert len(read_back.raw_body) == len(large_body)

    def test_unicode_and_multilingual_content_integrity(self, tmp_path: Path):
        """Test reading and writing content in Japanese, Arabic, Cyrillic, and Emojis."""
        vault = tmp_path / "vault"
        vault.mkdir()
        manager = VaultManager(vault)

        unicode_content = """# 多言語テスト (Multilingual Test)

- 日本語: こんにちは世界、量子コンピューティング
- Русский: Привет мир, искусственный интеллект
- العربية: مرحباً بالعالم، الذكاء الاصطناعي
- Emojis: 🌟🚀🤖📚🔥✨
- Math: $\\sum_{i=1}^n x_i = \\int_0^\\infty f(t) dt$
"""
        note = manager.write_note(
            "50-knowledge/Multilingual.md",
            unicode_content,
            mode="overwrite",
            metadata={"tags": ["i18n", "unicode", "日本語"]},
        )

        read_back = manager.read_note("50-knowledge/Multilingual.md")
        assert "こんにちは世界" in read_back.raw_body
        assert "Привет мир" in read_back.raw_body
        assert "مرحباً بالعالم" in read_back.raw_body
        assert "🚀🤖" in read_back.raw_body
        assert "日本語" in read_back.metadata.tags

    def test_prepend_mode_on_existing_note(self, tmp_path: Path):
        """Test prepending content adds text before previous body."""
        vault = tmp_path / "vault"
        vault.mkdir()
        manager = VaultManager(vault)

        manager.write_note("test.md", "Original Bottom Content", mode="overwrite")
        note = manager.write_note("test.md", "New Top Content", mode="prepend")

        assert note.raw_body.startswith("New Top Content")
        assert note.raw_body.endswith("Original Bottom Content")

    def test_multiple_daily_appends_ordering(self, tmp_path: Path):
        """Test multiple consecutive daily log appends maintain chronological order."""
        vault = tmp_path / "vault"
        vault.mkdir()
        manager = VaultManager(vault)

        manager.append_daily_log("Task 1 completed", date_str="2026-08-15")
        manager.append_daily_log("Task 2 completed", date_str="2026-08-15")
        manager.append_daily_log("Task 3 completed", date_str="2026-08-15")

        note = manager.read_note("10-daily/2026-08-15.md")
        assert "Task 1 completed" in note.content
        assert "Task 2 completed" in note.content
        assert "Task 3 completed" in note.content
        assert note.content.find("Task 1") < note.content.find("Task 2") < note.content.find("Task 3")
