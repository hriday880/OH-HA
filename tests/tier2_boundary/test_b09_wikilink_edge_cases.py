"""
Boundary Test 9: Wikilink Parsing & Backlink Edge Cases.
Tests unclosed wikilinks, links with punctuation, special characters, and code block isolation.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from bot.vault.links import BacklinkGraph, extract_wikilinks


class TestBoundary09WikilinkEdgeCases:
    """Boundary tests for Feature 9 (Wikilinks)."""

    def test_unclosed_wikilink_brackets(self):
        """Test text with unclosed [[wikilink brackets does not raise exception."""
        text = "This has [[Unclosed Link and some regular text."
        links = extract_wikilinks(text)
        assert links == []

    def test_wikilinks_with_complex_punctuation(self):
        """Test links with parentheses, colons, hyphens, and exclamation marks."""
        text = "Check out [[Project: Apollo-Next (v2.0)!|Apollo 2.0]]"
        links = extract_wikilinks(text)
        assert len(links) == 1
        assert links[0].target == "Project: Apollo-Next (v2.0)!"
        assert links[0].alias == "Apollo 2.0"

    def test_empty_wikilink_brackets(self):
        """Test empty [[]] does not create empty target link."""
        text = "Empty link [[]] and valid link [[ValidTarget]]"
        links = extract_wikilinks(text)
        assert len(links) == 1
        assert links[0].target == "ValidTarget"

    def test_backlink_graph_on_empty_vault(self, tmp_path: Path):
        """Test backlink graph initialization on empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        graph = BacklinkGraph(empty_dir)
        assert graph.get_backlinks("Anything") == []

    def test_cyclical_wikilinks_graph_stability(self, tmp_path: Path):
        """Test cyclical links (A links to B, B links to A) do not cause recursion errors."""
        vault = tmp_path / "cycle_vault"
        vault.mkdir()
        (vault / "NoteA.md").write_text("Links to [[NoteB]]\n", encoding="utf-8")
        (vault / "NoteB.md").write_text("Links to [[NoteA]]\n", encoding="utf-8")

        graph = BacklinkGraph(vault)
        assert "NoteA.md" in graph.get_backlinks("NoteB")
        assert "NoteB.md" in graph.get_backlinks("NoteA")
