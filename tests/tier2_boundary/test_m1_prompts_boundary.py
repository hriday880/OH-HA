"""
Tier 2 Boundary Tests: Feature 3 - Hermes Tool Calling & Prompt Engine.
"""

import unittest

from bot.agent.prompts import HermesPrompts, OpenHumanPrompts


class TestPromptsBoundary(unittest.TestCase):
    """Tier 2 Boundary tests for prompts and XML tag parsing."""

    def test_parse_tool_calls_empty_or_none(self):
        """Test parsing tool calls from empty or None text."""
        self.assertEqual(HermesPrompts.parse_tool_calls_from_text(""), [])
        self.assertEqual(HermesPrompts.parse_tool_calls_from_text(None), [])
        self.assertEqual(HermesPrompts.parse_tool_calls_from_text("Just regular text without any tags"), [])

    def test_parse_tool_calls_malformed_json_fallback(self):
        """Test fallback behavior when <tool_call> contains relaxed/broken JSON."""
        bad_json = """
<tool_call>
{"name": "read_note", "arguments": "Daily/note.md"}
</tool_call>
"""
        calls = HermesPrompts.parse_tool_calls_from_text(bad_json)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "read_note")
        self.assertEqual(calls[0]["arguments"], {"raw_arguments": "Daily/note.md"})

    def test_extract_scratchpad_alternative_tags(self):
        """Test extracting thoughts with <scratch_pad> and <thinking> tags."""
        t1 = "<scratch_pad>Need to search knowledge base</scratch_pad>Here is what I found."
        thought1, clean1 = HermesPrompts.extract_scratchpad(t1)
        self.assertEqual(thought1, "Need to search knowledge base")
        self.assertEqual(clean1, "Here is what I found.")

        t2 = "<thinking>Analyzing user question</thinking>The answer is 42."
        thought2, clean2 = HermesPrompts.extract_scratchpad(t2)
        self.assertEqual(thought2, "Analyzing user question")
        self.assertEqual(clean2, "The answer is 42.")

    def test_extract_scratchpad_with_tool_calls_removal(self):
        """Test that tool calls and thoughts are removed from clean text."""
        mixed = """
<thought>Step 1: check vault</thought>
<tool_call>{"name": "list_notes", "arguments": {}}</tool_call>
I am checking your notes now.
"""
        thought, clean = HermesPrompts.extract_scratchpad(mixed)
        self.assertEqual(thought, "Step 1: check vault")
        self.assertEqual(clean, "I am checking your notes now.")

    def test_format_tools_declaration_empty_list(self):
        """Test format_tools_declaration with empty list returns empty string."""
        self.assertEqual(HermesPrompts.format_tools_declaration([]), "")


if __name__ == "__main__":
    unittest.main()
