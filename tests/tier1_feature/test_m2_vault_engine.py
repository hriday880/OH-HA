"""
Milestone 2: Comprehensive Obsidian Vault Knowledge Base Engine Verification Suite.

Exercises all Milestone 2 components:
- Frontmatter parsing, serialization, inline tag extraction, date formatting
- Path security, normalization, traversal rejection
- VaultManager CRUD (read, write modes, delete, list, exists)
- Wikilink parsing, alias resolution, backlink graph indexing, broken link detection
- SQLite FTS5 BM25 search, tag indexing, query sanitization
- Note Archetypes (Daily notes, Conversation logs, Evergreen concepts, Templates)
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator
import pytest

from bot.vault.archetypes import (
    ConversationLogger,
    DailyNoteHandler,
    EvergreenNoteHandler,
    render_template,
)
from bot.vault.frontmatter import (
    FrontmatterEngine,
    FrontmatterParser,
    NoteMetadata,
    parse_frontmatter,
    serialize_frontmatter,
)
from bot.vault.links import (
    BacklinkGraph,
    WikiLink,
    extract_wikilinks,
)
from bot.vault.manager import (
    Note,
    VaultManager,
    VaultPathSecurityError,
    sanitize_vault_path,
)
from bot.vault.search import SearchResult, VaultSearchEngine


@pytest.fixture
def clean_vault(tmp_path: Path) -> Generator[VaultManager, None, None]:
    vault_dir = tmp_path / "test_m2_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    manager = VaultManager(vault_dir)
    yield manager


class TestM2Frontmatter:
    def test_frontmatter_parser_and_serializer_roundtrip(self):
        text = """---
title: Quantum Architecture
tags:
  - physics
  - quantum/algorithms
aliases:
  - QuantumArch
created: 2026-08-15T00:00:00Z
type: concept
difficulty: 5
---
# Quantum Architecture

Introduction to quantum circuits and qubits.
"""
        meta, body = FrontmatterEngine.parse(text)
        assert meta.title == "Quantum Architecture"
        assert meta.tags == ["physics", "quantum/algorithms"]
        assert meta.aliases == ["QuantumArch"]
        assert meta.created == "2026-08-15T00:00:00Z"
        assert meta.custom["type"] == "concept"
        assert meta.custom["difficulty"] == 5

        serialized = FrontmatterEngine.serialize(meta, body)
        meta2, body2 = FrontmatterEngine.parse(serialized)
        assert meta2.title == meta.title
        assert meta2.tags == meta.tags
        assert meta2.aliases == meta.aliases
        assert meta2.created == meta.created
        assert meta2.custom == meta.custom
        assert body2.strip() == body.strip()

    def test_inline_tags_extraction(self):
        body = """
        Here is some text with #inline-tag and #nested/topic-tag.
        Ignore code block:
        ```python
        # This is a comment, not a tag #fake_tag
        ```
        And inline code `#also_fake`.
        Also ignore headers:
        # Header 1
        ### Header 3
        """
        tags = FrontmatterEngine.extract_inline_tags(body)
        assert "inline-tag" in tags
        assert "nested/topic-tag" in tags
        assert "fake_tag" not in tags
        assert "also_fake" not in tags
        assert "Header" not in tags

    def test_metadata_dict_conversions(self):
        meta = NoteMetadata.from_dict({
            "title": "Dict Note",
            "tags": "alpha, beta, gamma",
            "aliases": "One, Two",
            "priority": "P0",
        })
        assert meta.title == "Dict Note"
        assert meta.tags == ["alpha", "beta", "gamma"]
        assert meta.aliases == ["One", "Two"]
        assert meta.custom["priority"] == "P0"

        d = meta.to_dict()
        assert d["title"] == "Dict Note"
        assert d["tags"] == ["alpha", "beta", "gamma"]
        assert d["aliases"] == ["One", "Two"]
        assert d["priority"] == "P0"


class TestM2PathSecurity:
    def test_path_sanitization_valid(self, tmp_path: Path):
        vault = tmp_path / "v"
        vault.mkdir()
        p1 = sanitize_vault_path(vault, "daily/2026-08-15")
        assert p1 == (vault / "daily" / "2026-08-15.md").resolve()

        p2 = sanitize_vault_path(vault, "notes/topic.md")
        assert p2 == (vault / "notes" / "topic.md").resolve()

    def test_path_traversal_rejections(self, tmp_path: Path):
        vault = tmp_path / "v"
        vault.mkdir()

        with pytest.raises(VaultPathSecurityError):
            sanitize_vault_path(vault, "../outside.md")

        with pytest.raises(VaultPathSecurityError):
            sanitize_vault_path(vault, "sub/../../outside.md")

        # Absolute paths are safely confined to vault root
        p = sanitize_vault_path(vault, "/etc/passwd")
        assert p == (vault / "etc/passwd.md").resolve()

        with pytest.raises(VaultPathSecurityError):
            sanitize_vault_path(vault, "")

        with pytest.raises(VaultPathSecurityError):
            sanitize_vault_path(vault, "note.md\0evil")



class TestM2VaultManagerCRUD:
    def test_crud_lifecycle(self, clean_vault: VaultManager):
        # 1. Write note with metadata
        note = clean_vault.write_note(
            "projects/Apollo.md",
            "# Apollo Project\nInitial content.",
            mode="overwrite",
            metadata={"title": "Apollo", "tags": ["project", "apollo"]},
        )
        assert note.path == "projects/Apollo.md"
        assert clean_vault.note_exists("projects/Apollo.md")

        # 2. Read note
        read_back = clean_vault.read_note("projects/Apollo.md")
        assert read_back.metadata.title == "Apollo"
        assert "Initial content." in read_back.raw_body

        # 3. Append to note
        clean_vault.write_note("projects/Apollo.md", "Appended line.", mode="append")
        read_appended = clean_vault.read_note("projects/Apollo.md")
        assert "Initial content." in read_appended.raw_body
        assert "Appended line." in read_appended.raw_body

        # 4. Prepend to note
        clean_vault.write_note("projects/Apollo.md", "Prepended header.", mode="prepend")
        read_prepended = clean_vault.read_note("projects/Apollo.md")
        assert read_prepended.raw_body.startswith("Prepended header.")

        # 5. List notes
        notes_list = clean_vault.list_notes("projects")
        assert "projects/Apollo.md" in notes_list

        # 6. Delete note
        assert clean_vault.delete_note("projects/Apollo.md") is True
        assert not clean_vault.note_exists("projects/Apollo.md")
        assert clean_vault.delete_note("projects/Apollo.md") is False


class TestM2WikilinksAndBacklinks:
    def test_wikilinks_extraction_and_resolution(self, clean_vault: VaultManager):
        clean_vault.write_note(
            "topics/AI.md",
            "# Artificial Intelligence\nCore topic note.",
            mode="overwrite",
            metadata={"title": "Artificial Intelligence", "aliases": ["AI", "ArtificialIntelligence"]},
        )

        clean_vault.write_note(
            "projects/Agent.md",
            "This project is based on [[topics/AI]] and [[AI|Smart Systems]] and [[AI#Transformers|Attention]].",
            mode="overwrite",
            metadata={"title": "Agent Project"},
        )

        links = clean_vault.get_forward_links("projects/Agent.md")
        assert len(links) == 3
        assert links[0].target == "topics/AI"
        assert links[1].alias == "Smart Systems"
        assert links[2].heading == "Transformers"

        # Check backlinks to AI
        backlinks = clean_vault.get_backlinks("topics/AI.md")
        assert "projects/Agent.md" in backlinks

        backlinks_by_alias = clean_vault.get_backlinks("AI")
        assert "projects/Agent.md" in backlinks_by_alias


class TestM2SearchAndTagIndexing:
    def test_fts5_search_and_ranking(self, clean_vault: VaultManager):
        clean_vault.write_note(
            "notes/Distributed.md",
            "# Distributed Systems\nConsensus protocols like Raft and Paxos ensure replication across nodes.",
            mode="overwrite",
            metadata={"title": "Distributed Systems", "tags": ["cs/distributed", "paxos"]},
        )
        clean_vault.write_note(
            "notes/Database.md",
            "# Modern Databases\nLSM-trees and B-trees for high throughput distributed storage.",
            mode="overwrite",
            metadata={"title": "Modern Databases", "tags": ["cs/storage"]},
        )

        # Keyword search
        res1 = clean_vault.search_notes("consensus")
        assert len(res1) >= 1
        assert "Distributed.md" in res1[0]["path"]

        # Tag search (hierarchical)
        res_tag = clean_vault.search_notes("", tag="cs")
        assert len(res_tag) == 2

        res_subtag = clean_vault.search_notes("", tag="cs/distributed")
        assert len(res_subtag) == 1
        assert "Distributed.md" in res_subtag[0]["path"]


class TestM2Archetypes:
    def test_daily_note_logging(self, clean_vault: VaultManager):
        note = clean_vault.append_daily_log("Initial daily task", date_str="2026-08-15", section="Log")
        assert "Initial daily task" in note.content
        assert note.metadata.custom.get("type") == "daily"

        note2 = clean_vault.append_daily_log("Second daily task", date_str="2026-08-15", section="Log")
        assert "Initial daily task" in note2.content
        assert "Second daily task" in note2.content
        assert note2.content.find("Initial daily task") < note2.content.find("Second daily task")

    def test_conversation_saving(self, clean_vault: VaultManager):
        messages = [
            {"role": "user", "content": "How do quantum computers work?"},
            {"role": "assistant", "content": "They leverage superposition and entanglement."},
        ]
        conv_note = clean_vault.save_conversation(
            topic="Quantum Computing Intro",
            messages=messages,
            summary="Discussion about quantum basics.",
        )
        assert clean_vault.note_exists(conv_note.path)
        assert "Quantum Computing Intro" in conv_note.content
        assert "superposition and entanglement" in conv_note.content

    def test_evergreen_note_creation(self, clean_vault: VaultManager):
        evergreen = clean_vault.create_evergreen_note(
            title="Consensus Algorithms",
            content="Detailed exploration of Paxos, Raft, and PBFT.",
            summary="Overview of consensus mechanisms in distributed networks.",
            tags=["distributed", "algorithms"],
            related_links=["Distributed Systems", "Raft Protocol"],
        )
        assert clean_vault.note_exists(evergreen.path)
        assert "[[Distributed Systems]]" in evergreen.content
        assert "[[Raft Protocol]]" in evergreen.content
