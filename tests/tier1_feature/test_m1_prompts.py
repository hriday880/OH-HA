"""
Tier 1 Feature Tests: Feature 3 - Hermes Tool Calling & Prompt Engine.
"""

import json
import unittest

from bot.agent.prompts import HermesPrompts, OpenHumanPrompts
from bot.agent.tools import ToolDefinition, STANDARD_OBSIDIAN_TOOLS


class TestPromptsFeature(unittest.TestCase):
    """Tier 1 Unit tests for Hermes 3 ChatML XML formatting and prompt generation."""

    def test_format_tools_declaration(self):
        """Test formatting ToolDefinition list into Hermes <tools> XML block."""
        tools = [
            ToolDefinition(
                name="read_note",
                description="Read note from vault",
                parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            ),
            ToolDefinition(
                name="sync_vault",
                description="Sync vault with git",
                parameters={"type": "object", "properties": {}},
            ),
        ]
        xml = HermesPrompts.format_tools_declaration(tools)
        self.assertTrue(xml.startswith("<tools>"))
        self.assertTrue(xml.endswith("</tools>"))
        self.assertIn('"name": "read_note"', xml)
        self.assertIn('"name": "sync_vault"', xml)

    def test_parse_single_tool_call(self):
        """Test extracting single <tool_call> block."""
        sample_output = """
I will now read your daily note.
<tool_call>
{"name": "read_note", "arguments": {"path": "Daily/2026-08-14.md"}}
</tool_call>
"""
        calls = HermesPrompts.parse_tool_calls_from_text(sample_output)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "read_note")
        self.assertEqual(calls[0]["arguments"], {"path": "Daily/2026-08-14.md"})

    def test_parse_multiple_tool_calls(self):
        """Test extracting multiple sequential <tool_call> blocks."""
        sample_output = """
<tool_call>
{"name": "search_notes", "arguments": {"query": "project"}}
</tool_call>
Some intermediate thoughts...
<tool_call>
{"name": "read_note", "arguments": {"path": "Projects/Hermes.md"}}
</tool_call>
"""
        calls = HermesPrompts.parse_tool_calls_from_text(sample_output)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["name"], "search_notes")
        self.assertEqual(calls[1]["name"], "read_note")
        self.assertEqual(calls[1]["arguments"]["path"], "Projects/Hermes.md")

    def test_format_tool_response(self):
        """Test generating <tool_response> XML."""
        res_xml = HermesPrompts.format_tool_response(
            "write_note", {"status": "success", "bytes": 100}
        )
        self.assertTrue(res_xml.startswith("<tool_response>"))
        self.assertTrue(res_xml.endswith("</tool_response>"))
        self.assertIn('"name": "write_note"', res_xml)
        self.assertIn('"status": "success"', res_xml)

    def test_extract_scratchpad_thought(self):
        """Test extracting <thought> inner monologue from output text."""
        raw_text = """<thought>
The user wants to check yesterday's progress. I need to find the daily note for 2026-08-13.
</thought>
Here is the summary of what you did yesterday!"""
        thought, clean_text = HermesPrompts.extract_scratchpad(raw_text)
        self.assertIsNotNone(thought)
        self.assertIn("user wants to check yesterday's progress", thought)
        self.assertEqual(clean_text, "Here is the summary of what you did yesterday!")
        self.assertNotIn("<thought>", clean_text)

    def test_build_system_prompt(self):
        """Test assembling complete OpenHuman system prompt."""
        system_prompt = OpenHumanPrompts.build_system_prompt(
            persona_instructions="- Name: OpenHuman\n- Tone: Friendly",
            memory_context="### Daily Log: 2026-08-14\nTasks completed.",
            tools=STANDARD_OBSIDIAN_TOOLS,
            user_name="Alice",
        )
        self.assertIn("Alice", system_prompt)
        self.assertIn("OpenHuman", system_prompt)
        self.assertIn("Available Tools", system_prompt)
        self.assertIn("<tools>", system_prompt)
        self.assertIn("read_note", system_prompt)


if __name__ == "__main__":
    unittest.main()
