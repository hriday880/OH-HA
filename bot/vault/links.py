"""
Obsidian Wikilink Parsing & Bidirectional Backlink Graph Engine.

Parses Wikilinks ([[Note]], [[Note|Alias]], [[Note#Heading|Alias]]), resolves
target note paths using Obsidian vault resolution rules (shortest path, basename match,
alias mappings), and maintains a bidirectional backlink graph.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from bot.vault.frontmatter import FrontmatterEngine

logger = logging.getLogger(__name__)


@dataclass
class WikiLink:
    """
    Structured representation of a parsed Obsidian Wikilink.
    """

    raw: str
    target: str
    alias: Optional[str] = None
    heading: Optional[str] = None
    line_number: int = 1

    @property
    def note_name(self) -> str:
        """Base note name without directory or heading."""
        clean = self.target.split("/")[-1]
        if clean.endswith(".md"):
            clean = clean[:-3]
        return clean


# Alias for type flexibility
Wikilink = WikiLink


@dataclass
class Backlink:
    """
    Incoming link reference pointing to a target note.
    """

    source_path: str
    source_title: str
    target: str
    target_path: Optional[str] = None
    alias: Optional[str] = None
    heading: Optional[str] = None
    context_snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_title": self.source_title,
            "target": self.target,
            "target_path": self.target_path,
            "alias": self.alias,
            "heading": self.heading,
            "context_snippet": self.context_snippet,
        }


WIKILINK_REGEX = re.compile(
    r"\[\[\s*([^\]|#\n]+?)\s*(?:#([^\]|\n]+?))?\s*(?:\|\s*([^\]\n]+?)\s*)?\]\]"
)
INLINE_CODE_REGEX = re.compile(r"`[^`]*`")
CODE_BLOCK_REGEX = re.compile(r"```[\s\S]*?```")


def extract_wikilinks(text: str) -> List[WikiLink]:
    """
    Extract all valid Wikilinks from markdown text, ignoring code blocks and inline code.
    """
    if not text or not text.strip():
        return []

    # First, replace code blocks and inline code with whitespace to maintain line positions
    masked_text = CODE_BLOCK_REGEX.sub(lambda m: " " * len(m.group(0)), text)
    masked_text = INLINE_CODE_REGEX.sub(lambda m: " " * len(m.group(0)), masked_text)

    links: List[WikiLink] = []
    lines = masked_text.splitlines()

    for line_idx, line in enumerate(lines, start=1):
        for match in WIKILINK_REGEX.finditer(line):
            raw = match.group(0)
            target = match.group(1).strip() if match.group(1) else ""
            if not target:
                continue

            heading = match.group(2).strip() if match.group(2) else None
            alias = match.group(3).strip() if match.group(3) else None

            links.append(
                WikiLink(
                    raw=raw,
                    target=target,
                    alias=alias,
                    heading=heading,
                    line_number=line_idx,
                )
            )

    return links


class BacklinkGraph:
    """
    Bidirectional Link and Backlink Graph for an Obsidian Vault.
    """

    def __init__(self, vault_path: Optional[Path] = None) -> None:
        self.vault_path = Path(vault_path).resolve() if vault_path else None
        self._forward_links: Dict[str, List[WikiLink]] = {}
        self._backlinks: Dict[str, Set[str]] = {}
        self._note_titles: Dict[str, str] = {}
        self._aliases_to_path: Dict[str, str] = {}
        self._stem_to_paths: Dict[str, List[str]] = {}
        self._all_paths: Set[str] = set()

        if self.vault_path and self.vault_path.is_dir():
            self.build_graph()

    def build_graph(self) -> None:
        """
        Scan all markdown notes in vault, index metadata, and construct link relationships.
        """
        self.clear()
        if not self.vault_path or not self.vault_path.is_dir():
            return

        note_contents: Dict[str, str] = {}

        # 1. First pass: Collect all note files and register stems / titles / aliases
        for md_file in self.vault_path.rglob("*.md"):
            if md_file.name.startswith(".") or ".obsidian" in str(md_file) or ".git" in str(md_file):
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception as e:
                logger.debug(f"Error reading {md_file} for backlink graph: {e}")
                continue

            rel_path = str(md_file.relative_to(self.vault_path)).replace("\\", "/")
            note_contents[rel_path] = content
            self._register_note_metadata(rel_path, content)

        # 2. Second pass: Extract wikilinks and build forward & backlink index
        for rel_path, content in note_contents.items():
            self._index_note_links(rel_path, content)

    def clear(self) -> None:
        """Reset internal graph state."""
        self._forward_links.clear()
        self._backlinks.clear()
        self._note_titles.clear()
        self._aliases_to_path.clear()
        self._stem_to_paths.clear()
        self._all_paths.clear()

    def _register_note_metadata(self, rel_path: str, content: str) -> None:
        """Register note stem, title, and frontmatter aliases."""
        self._all_paths.add(rel_path)
        stem = Path(rel_path).stem
        if stem not in self._stem_to_paths:
            self._stem_to_paths[stem] = []
        if rel_path not in self._stem_to_paths[stem]:
            self._stem_to_paths[stem].append(rel_path)

        meta, _ = FrontmatterEngine.parse(content)
        title = meta.title or stem
        self._note_titles[rel_path] = title

        # Map title and aliases to relative path
        self._aliases_to_path[title.lower()] = rel_path
        self._aliases_to_path[stem.lower()] = rel_path
        self._aliases_to_path[rel_path.lower()] = rel_path

        for alias in meta.aliases:
            if alias:
                self._aliases_to_path[alias.lower()] = rel_path

    def _index_note_links(self, rel_path: str, content: str) -> None:
        """Extract links from note content and record forward and backlinks."""
        links = extract_wikilinks(content)
        self._forward_links[rel_path] = links

        for link in links:
            target_key = link.target
            # Index under raw target string
            if target_key not in self._backlinks:
                self._backlinks[target_key] = set()
            self._backlinks[target_key].add(rel_path)

            # Index under stem / resolved key
            target_stem = Path(target_key).stem
            if target_stem not in self._backlinks:
                self._backlinks[target_stem] = set()
            self._backlinks[target_stem].add(rel_path)

            # Also index under resolved relative path if resolvable
            resolved = self.resolve_link(link.target)
            if resolved:
                if resolved not in self._backlinks:
                    self._backlinks[resolved] = set()
                self._backlinks[resolved].add(rel_path)
                res_stem = Path(resolved).stem
                if res_stem not in self._backlinks:
                    self._backlinks[res_stem] = set()
                self._backlinks[res_stem].add(rel_path)

    def resolve_link(self, target: str, current_note: Optional[str] = None) -> Optional[str]:
        """
        Resolve a link target string to a relative note path in the vault.
        Rules:
        1. Exact relative path match (with or without .md)
        2. Alias match from frontmatter
        3. Stem / title match across vault
        4. Relative to current_note folder
        5. Case-insensitive fallback
        """
        if not target:
            return None

        clean_target = target.strip().replace("\\", "/")
        clean_target_md = clean_target if clean_target.endswith(".md") else f"{clean_target}.md"

        # 1. Exact match in all paths
        if clean_target_md in self._all_paths:
            return clean_target_md
        if clean_target in self._all_paths:
            return clean_target

        # 2. Relative to current_note directory
        if current_note:
            current_dir = Path(current_note).parent
            candidate = str((current_dir / clean_target_md).as_posix()).lstrip("./")
            if candidate in self._all_paths:
                return candidate

        # 3. Stem match
        stem = Path(clean_target).stem
        if stem in self._stem_to_paths and self._stem_to_paths[stem]:
            return self._stem_to_paths[stem][0]

        # 4. Alias or lowercased title match
        lower_key = clean_target.lower()
        if lower_key in self._aliases_to_path:
            return self._aliases_to_path[lower_key]

        stem_lower = stem.lower()
        if stem_lower in self._aliases_to_path:
            return self._aliases_to_path[stem_lower]

        # 5. Case-insensitive search through all paths
        for path in self._all_paths:
            if path.lower() == clean_target_md.lower() or Path(path).stem.lower() == stem_lower:
                return path

        return None

    def get_backlinks(self, note_identifier: str) -> List[str]:
        """
        Retrieve sorted list of relative note paths that contain wikilinks pointing to this note.
        `note_identifier` can be a note title, filename, stem, or relative path.
        """
        if not note_identifier:
            return []

        results: Set[str] = set()

        # Check raw identifier
        if note_identifier in self._backlinks:
            results.update(self._backlinks[note_identifier])

        # Check stem
        stem = Path(note_identifier).stem
        if stem in self._backlinks:
            results.update(self._backlinks[stem])

        # Check resolved path
        resolved = self.resolve_link(note_identifier)
        if resolved and resolved in self._backlinks:
            results.update(self._backlinks[resolved])

        # Check case-insensitive
        ident_lower = note_identifier.lower()
        for k, sources in self._backlinks.items():
            if k.lower() == ident_lower or Path(k).stem.lower() == ident_lower:
                results.update(sources)

        return sorted(list(results))

    def get_forward_links(self, rel_path: str) -> List[WikiLink]:
        """Retrieve list of outgoing wikilinks from a note."""
        clean_path = rel_path.replace("\\", "/").lstrip("/")
        if not clean_path.endswith(".md"):
            clean_path = f"{clean_path}.md"
        return self._forward_links.get(clean_path, [])

    def update_note_links(self, rel_path: str, content: str) -> None:
        """Incrementally update links and backlinks for a modified or added note."""
        clean_path = rel_path.replace("\\", "/").lstrip("/")
        if not clean_path.endswith(".md"):
            clean_path = f"{clean_path}.md"

        # Remove old backlinks generated by this note
        for target, sources in self._backlinks.items():
            sources.discard(clean_path)

        self._register_note_metadata(clean_path, content)
        self._index_note_links(clean_path, content)

    def remove_note(self, rel_path: str) -> None:
        """Remove note from link graph on deletion."""
        clean_path = rel_path.replace("\\", "/").lstrip("/")
        if not clean_path.endswith(".md"):
            clean_path = f"{clean_path}.md"

        self._all_paths.discard(clean_path)
        self._forward_links.pop(clean_path, None)
        title = self._note_titles.pop(clean_path, None)
        if title:
            self._aliases_to_path.pop(title.lower(), None)

        stem = Path(clean_path).stem
        if stem in self._stem_to_paths:
            self._stem_to_paths[stem] = [p for p in self._stem_to_paths[stem] if p != clean_path]
            if not self._stem_to_paths[stem]:
                self._stem_to_paths.pop(stem, None)

        # Remove as source in backlinks
        for target, sources in self._backlinks.items():
            sources.discard(clean_path)

    def get_unresolved_links(self) -> Dict[str, List[str]]:
        """Identify broken/unresolved wikilinks and their referring notes."""
        unresolved: Dict[str, List[str]] = {}
        for source_path, links in self._forward_links.items():
            for link in links:
                if not self.resolve_link(link.target, current_note=source_path):
                    if link.target not in unresolved:
                        unresolved[link.target] = []
                    if source_path not in unresolved[link.target]:
                        unresolved[link.target].append(source_path)
        return unresolved


# Alias for protocol and contract consistency
LinkGraph = BacklinkGraph
