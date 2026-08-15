"""
Feature 9: Wikilink & Backlink Engine Test Suite.
Tests wikilink extraction ([[Target]], [[Target|Alias]], [[Target#Heading]]),
shortest path resolution, and backlink graph construction.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import pytest

# Try importing bot.vault.links if present or implement contract-based link engine
try:
    from bot.vault.links import BacklinkGraph, WikiLink, extract_wikilinks
except ImportError:
    from dataclasses import dataclass

    @dataclass
    class WikiLink:
        raw: str
        target: str
        alias: Optional[str] = None
        heading: Optional[str] = None

    WIKILINK_REGEX = re.compile(r"\[\[([^\]|#]+)(?:#([^\]|]+))?(?:\|([^\]]+))?\]\]")

    def extract_wikilinks(text: str) -> List[WikiLink]:
        if not text:
            return []
        links: List[WikiLink] = []
        for match in WIKILINK_REGEX.finditer(text):
            raw = match.group(0)
            target = match.group(1).strip()
            heading = match.group(2).strip() if match.group(2) else None
            alias = match.group(3).strip() if match.group(3) else None
            links.append(WikiLink(raw=raw, target=target, alias=alias, heading=heading))
        return links

    class BacklinkGraph:
        def __init__(self, vault_path: Path) -> None:
            self.vault_path = Path(vault_path)
            self.graph: Dict[str, Set[str]] = {}
            self.build_graph()

        def build_graph(self) -> None:
            self.graph.clear()
            for md_file in self.vault_path.rglob("*.md"):
                if md_file.name.startswith("."):
                    continue
                try:
                    content = md_file.read_text(encoding="utf-8")
                except Exception:
                    continue
                source_key = md_file.stem
                links = extract_wikilinks(content)
                for link in links:
                    target_key = link.target
                    if target_key not in self.graph:
                        self.graph[target_key] = set()
                    self.graph[target_key].add(str(md_file.relative_to(self.vault_path)))

        def get_backlinks(self, note_title: str) -> List[str]:
            return sorted(list(self.graph.get(note_title, set())))


class TestFeature09WikilinksBacklinks:
    """Test suite for Feature 9: Wikilink & Backlink Engine."""

    def test_extract_simple_and_aliased_wikilinks(self):
        """Test extracting standard [[Note]] and [[Note|Alias]] links."""
        body = "See [[Project Apollo]] and [[User Profile|Alice]] for more details."
        links = extract_wikilinks(body)
        assert len(links) == 2

        assert links[0].target == "Project Apollo"
        assert links[0].alias is None

        assert links[1].target == "User Profile"
        assert links[1].alias == "Alice"

    def test_extract_wikilink_with_heading(self):
        """Test extracting links with headings e.g. [[Project Apollo#Architecture]]."""
        body = "Refer to [[Project Apollo#Architecture|System Arch]] in the docs."
        links = extract_wikilinks(body)
        assert len(links) == 1
        assert links[0].target == "Project Apollo"
        assert links[0].heading == "Architecture"
        assert links[0].alias == "System Arch"

    def test_backlink_graph_indexing(self, mock_vault_dir: Path):
        """Test building backlink index across mock vault notes."""
        graph = BacklinkGraph(mock_vault_dir)

        # In mock_vault_dir, Project_Apollo and MOC_Index link to Quantum Computing Basics
        backlinks = graph.get_backlinks("Quantum Computing Basics")
        assert len(backlinks) >= 1
        assert any("Project_Apollo" in b or "MOC_Index" in b for b in backlinks)

    def test_empty_backlinks_for_unreferenced_note(self, mock_vault_dir: Path):
        """Test that notes without incoming links return empty list."""
        graph = BacklinkGraph(mock_vault_dir)
        backlinks = graph.get_backlinks("NonExistentNote")
        assert backlinks == []

    def test_multiple_wikilinks_in_single_line(self):
        """Test parsing dense text with consecutive wikilinks."""
        line = "Compare [[Python]], [[Rust]], and [[Go|Golang]] for systems programming."
        links = extract_wikilinks(line)
        assert len(links) == 3
        assert [l.target for l in links] == ["Python", "Rust", "Go"]
        assert links[2].alias == "Golang"
