"""
Feature 3: Hermes Tool Calling & Prompt Engine Test Suite.
Tests Hermes 3 ChatML XML formatting (<tools>, <tool_call>, <tool_response>),
thought extraction, and OpenHuman system prompts.
"""

from __future__ import annotations

import json
import pytest
from bot.agent.prompts import HermesPrompts, OpenHumanPrompts
from bot.agent.tools import STANDARD_OBSIDIAN_TOOLS, ToolDefinition


class TestFeature03HermesPrompts:
    """Test suite for Feature 3: Hermes Tool Calling and Prompt Engine."""

    def test_format_tools_declaration(self):
        """Test formatting of ToolDefinitions into Hermes <tools> XML block."""
        tools = [
            ToolDefinition(
                name="read_note",
                description="Read a note from the vault",
                parameters={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            )
        ]
        xml = HermesPrompts.format_tools_declaration(tools)
        assert xml.startswith("<tools>")
        assert xml.endswith("</tools>")
        assert "read_note" in xml
        assert "parameters" in xml

    def test_format_tool_response(self):
        """Test formatting tool output into <tool_response> XML tag."""
        res_xml = HermesPrompts.format_tool_response(
            tool_name="read_note",
            content={"title": "Test Note", "body": "Content here"},
        )
        assert res_xml.startswith("<tool_response>")
        assert res_xml.endswith("</tool_response>")
        assert "read_note" in res_xml
        assert "Test Note" in res_xml

    def test_parse_tool_calls_from_chatml_text(self):
        """Test extracting single and multiple <tool_call> tags from assistant text."""
        raw_text = """
        I will look up your profile and check your daily notes.
        <tool_call>
        {"name": "read_note", "arguments": {"path": "30-people/User_Profile.md"}}
        </tool_call>
        <tool_call>
        {"name": "search_notes", "arguments": {"query": "Apollo", "tag": "project"}}
        </tool_call>
        """
        calls = HermesPrompts.parse_tool_calls_from_text(raw_text)
        assert len(calls) == 2
        assert calls[0]["name"] == "read_note"
        assert calls[0]["arguments"] == {"path": "30-people/User_Profile.md"}
        assert calls[1]["name"] == "search_notes"
        assert calls[1]["arguments"] == {"query": "Apollo", "tag": "project"}

    def test_extract_thoughts_and_clean_text(self):
        """Test separating internal scratchpad thoughts from user-facing text."""
        text_with_thought = "<thought>The user wants to plan Apollo tasks.</thought>Here is the plan for Project Apollo."
        clean_text, thought = HermesPrompts.extract_thoughts_and_clean_text(text_with_thought)
        assert thought == "The user wants to plan Apollo tasks."
        assert clean_text == "Here is the plan for Project Apollo."

    def test_openhuman_system_prompt_builder(self):
        """Test OpenHuman system prompt includes persona, UTC time, and memory context."""
        prompt = OpenHumanPrompts.build_system_prompt(
            user_name="Alice",
            persona_name="Hermes Companion",
            user_profile="Prefers concise bullet points.",
            recent_notes=["10-daily/2026-08-14.md", "40-projects/Project_Apollo.md"],
            tools=STANDARD_OBSIDIAN_TOOLS,
        )
        assert "Alice" in prompt
        assert "Hermes Companion" in prompt
        assert "Prefers concise bullet points." in prompt
        assert "Project_Apollo.md" in prompt
        assert "<tools>" in prompt
        assert "write_note" in prompt
