"""
Boundary Test 3: Hermes ChatML XML & Parsing Boundaries.
Tests unclosed XML tags, malformed JSON inside tool calls, special characters, and empty buffers.
"""

from __future__ import annotations

import pytest
from bot.agent.prompts import HermesPrompts


class TestBoundary03HermesXML:
    """Boundary tests for Feature 3 (Hermes Prompts & XML)."""

    def test_unclosed_tool_call_tag_recovery(self):
        """Test unclosed <tool_call> tag is handled gracefully without crashing."""
        raw = "I will write note <tool_call>{\"name\": \"read_note\", \"arguments\": {\"path\": \"test.md\"}} (missing close tag)"
        # Should not crash, returns what it can extract
        calls = HermesPrompts.parse_tool_calls_from_text(raw)
        assert isinstance(calls, list)

    def test_malformed_json_inside_tool_call(self):
        """Test relaxed regex recovery when LLM produces slightly invalid JSON inside <tool_call>."""
        raw = "<tool_call>{\"name\": \"search_notes\", \"arguments\": {missing_quotes}}</tool_call>"
        calls = HermesPrompts.parse_tool_calls_from_text(raw)
        assert len(calls) == 1
        assert calls[0]["name"] == "search_notes"

    def test_special_characters_and_quotes_in_tool_args(self):
        """Test tool arguments containing escaped quotes, unicode, and newlines."""
        raw = """<tool_call>
        {"name": "write_note", "arguments": {"path": "10-daily/2026-08-15.md", "content": "Line 1\nLine 2: \\"Quotes\\" & emojis 🚀\n$$LaTeX$$"}}
        </tool_call>"""
        calls = HermesPrompts.parse_tool_calls_from_text(raw)
        assert len(calls) == 1
        assert calls[0]["name"] == "write_note"
        assert "Line 1" in calls[0]["arguments"]["content"]
        assert "🚀" in calls[0]["arguments"]["content"]

    def test_empty_and_whitespace_text_parsing(self):
        """Test parser handles empty string or whitespace-only text."""
        assert HermesPrompts.parse_tool_calls_from_text("") == []
        assert HermesPrompts.parse_tool_calls_from_text("   \n\t  ") == []
        clean, thought = HermesPrompts.extract_thoughts_and_clean_text("")
        assert clean == ""
        assert thought is None

    def test_nested_thought_tags_handling(self):
        """Test text with multiple or nested thought tags."""
        raw = "<thought>Thought 1</thought>Some text<thought>Thought 2</thought>Final answer."
        clean, thought = HermesPrompts.extract_thoughts_and_clean_text(raw)
        assert "Final answer." in clean
        assert "<thought>" not in clean
