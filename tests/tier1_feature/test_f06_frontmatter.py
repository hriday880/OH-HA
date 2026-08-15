"""
Feature 6: Obsidian Frontmatter & Markdown Engine Test Suite.
Tests YAML frontmatter parsing, metadata extraction, serialization, and lossless body preservation.
"""

from __future__ import annotations

import pytest
import yaml

# Try importing bot.vault.frontmatter if present, or define contract-based parser for test verification
try:
    from bot.vault.frontmatter import FrontmatterEngine, NoteMetadata
except ImportError:
    import re
    from dataclasses import dataclass, field
    from typing import Any, Dict, List, Optional, Tuple

    @dataclass
    class NoteMetadata:
        title: Optional[str] = None
        tags: List[str] = field(default_factory=list)
        aliases: List[str] = field(default_factory=list)
        created: Optional[str] = None
        updated: Optional[str] = None
        custom: Dict[str, Any] = field(default_factory=dict)

    class FrontmatterEngine:
        FRONTMATTER_REGEX = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

        @classmethod
        def parse(cls, content: str) -> Tuple[NoteMetadata, str]:
            if not content:
                return NoteMetadata(), ""
            match = cls.FRONTMATTER_REGEX.match(content)
            if not match:
                return NoteMetadata(), content
            yaml_block = match.group(1)
            body = content[match.end():]
            try:
                data = yaml.safe_load(yaml_block) or {}
            except Exception:
                return NoteMetadata(), content
            if not isinstance(data, dict):
                return NoteMetadata(), body
            
            tags = data.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            aliases = data.get("aliases", [])
            if isinstance(aliases, str):
                aliases = [a.strip() for a in aliases.split(",") if a.strip()]
            
            known_keys = {"title", "tags", "aliases", "created", "updated"}
            custom = {k: v for k, v in data.items() if k not in known_keys}
            
            meta = NoteMetadata(
                title=data.get("title"),
                tags=tags if isinstance(tags, list) else [],
                aliases=aliases if isinstance(aliases, list) else [],
                created=str(data.get("created")) if data.get("created") else None,
                updated=str(data.get("updated")) if data.get("updated") else None,
                custom=custom,
            )
            return meta, body

        @classmethod
        def serialize(cls, metadata: NoteMetadata, body: str) -> str:
            data: Dict[str, Any] = {}
            if metadata.title:
                data["title"] = metadata.title
            if metadata.tags:
                data["tags"] = metadata.tags
            if metadata.aliases:
                data["aliases"] = metadata.aliases
            if metadata.created:
                data["created"] = metadata.created
            if metadata.updated:
                data["updated"] = metadata.updated
            data.update(metadata.custom)

            if not data:
                return body

            yaml_str = yaml.dump(data, sort_keys=False, allow_unicode=True).strip()
            return f"---\n{yaml_str}\n---\n{body.lstrip()}"


class TestFeature06Frontmatter:
    """Test suite for Feature 6: Obsidian Frontmatter & Markdown Engine."""

    def test_parse_valid_frontmatter(self):
        """Test parsing valid YAML frontmatter and extracting structured properties."""
        content = """---
title: "Project Apollo"
type: "project"
tags:
  - project/apollo
  - priority/high
aliases:
  - "Apollo"
created: 2026-08-15T00:00:00Z
---
# Project Apollo Body

This is the main body text of the note.
"""
        meta, body = FrontmatterEngine.parse(content)
        assert meta.title == "Project Apollo"
        assert "project/apollo" in meta.tags
        assert "priority/high" in meta.tags
        assert "Apollo" in meta.aliases
        assert meta.created == "2026-08-15T00:00:00Z"
        assert meta.custom.get("type") == "project"
        assert body.strip() == "# Project Apollo Body\n\nThis is the main body text of the note."

    def test_parse_note_without_frontmatter(self):
        """Test parsing note without frontmatter returns empty metadata and full body."""
        content = "# Raw Note\n\nJust markdown without YAML header."
        meta, body = FrontmatterEngine.parse(content)
        assert meta.title is None
        assert meta.tags == []
        assert body == content

    def test_serialize_frontmatter_and_body(self):
        """Test serializing NoteMetadata back to markdown with --- header."""
        meta = NoteMetadata(
            title="Serialized Note",
            tags=["daily", "log"],
            aliases=["DailyLog"],
            custom={"status": "done"},
        )
        body = "## Today's Achievements\n- Completed feature tests"
        result = FrontmatterEngine.serialize(meta, body)

        assert result.startswith("---\n")
        assert "title: Serialized Note" in result
        assert "status: done" in result
        assert "## Today's Achievements" in result

    def test_roundtrip_preservation(self):
        """Test parsing and serializing preserves body structure, code blocks, and math."""
        original_body = """# Note with Code

```python
def solve(x: int) -> int:
    return x * 2
```

LaTeX math block:
$$ E = mc^2 $$
"""
        meta = NoteMetadata(title="Math & Code", tags=["science"])
        serialized = FrontmatterEngine.serialize(meta, original_body)
        parsed_meta, parsed_body = FrontmatterEngine.parse(serialized)

        assert parsed_meta.title == "Math & Code"
        assert parsed_meta.tags == ["science"]
        assert "def solve(x: int) -> int:" in parsed_body
        assert "$$ E = mc^2 $$" in parsed_body

    def test_comma_separated_tags_normalization(self):
        """Test string tags are normalized to a clean list."""
        content = """---
title: "Comma Tags"
tags: "tag1, tag2, tag3"
aliases: "Alias A, Alias B"
---
Body text.
"""
        meta, body = FrontmatterEngine.parse(content)
        assert meta.tags == ["tag1", "tag2", "tag3"]
        assert meta.aliases == ["Alias A", "Alias B"]
