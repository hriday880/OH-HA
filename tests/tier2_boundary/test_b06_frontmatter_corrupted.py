"""
Boundary Test 6: Corrupted Frontmatter & Malformed YAML.
Tests parsing notes with YAML syntax errors, missing closing delimiters, tabs, and non-dict frontmatter.
"""

from __future__ import annotations

import pytest
from bot.vault.frontmatter import FrontmatterEngine, NoteMetadata


class TestBoundary06CorruptedFrontmatter:
    """Boundary tests for Feature 6 (Frontmatter Engine)."""

    def test_corrupted_yaml_syntax_error_recovery(self):
        """Test parser does not crash on malformed YAML (e.g. invalid indentation or unquoted colons)."""
        content = """---
title: Broken YAML : : :: [[ bad
tags: [unclosed list
---
# Note Body After Broken Frontmatter

This body content must not be lost!
"""
        meta, body = FrontmatterEngine.parse(content)
        assert isinstance(meta, NoteMetadata)
        assert "This body content must not be lost!" in body

    def test_missing_closing_delimiter(self):
        """Test file starting with --- but missing the closing --- delimiter."""
        content = """---
title: Unclosed Frontmatter
No closing delimiter here
# Header
"""
        meta, body = FrontmatterEngine.parse(content)
        # Should treat whole file as body without throwing unhandled exception
        assert "Unclosed Frontmatter" in body or meta.title == "Unclosed Frontmatter"

    def test_multiple_horizontal_rules_in_body(self):
        """Test note containing multiple markdown horizontal rules (---) inside body."""
        content = """---
title: "Valid Title"
tags: ["rule-test"]
---
# Section 1
Content 1

---

# Section 2
Content 2

---

# Section 3
"""
        meta, body = FrontmatterEngine.parse(content)
        assert meta.title == "Valid Title"
        assert meta.tags == ["rule-test"]
        assert body.count("---") == 2
        assert "# Section 2" in body
        assert "# Section 3" in body

    def test_yaml_list_at_head_instead_of_dict(self):
        """Test frontmatter that parses into a list instead of a dict."""
        content = """---
- item 1
- item 2
---
# Body
"""
        meta, body = FrontmatterEngine.parse(content)
        assert isinstance(meta, NoteMetadata)
        assert "# Body" in body

    def test_empty_frontmatter_delimiters(self):
        """Test note with empty frontmatter block (--- followed immediately by ---)."""
        content = """---
---
# Pure Body
"""
        meta, body = FrontmatterEngine.parse(content)
        assert meta.title is None
        assert "# Pure Body" in body
