"""
Prompt Templates and Hermes 3 ChatML XML Formatting.

Implements native Hermes 3 ChatML XML tool tags (<tools>, <tool_call>, <tool_response>),
scratchpad / thought extraction, and OpenHuman persona system prompts.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from bot.agent.tools import ToolCall, ToolDefinition


class HermesPrompts:
    """
    Hermes 3 ChatML XML Prompt and Response Formatter.
    Handles <tools>, <tool_call>, <tool_response>, and reasoning scratchpads.
    """

    TOOL_CALL_REGEX = re.compile(
        r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL | re.IGNORECASE
    )
    THOUGHT_REGEX = re.compile(
        r"<(?:thought|scratch_pad|thinking)>\s*(.*?)\s*</(?:thought|scratch_pad|thinking)>",
        re.DOTALL | re.IGNORECASE,
    )

    @classmethod
    def format_tools_declaration(cls, tools: List[ToolDefinition]) -> str:
        """
        Format a list of ToolDefinition objects into Hermes ChatML <tools> XML block.
        Each tool is serialized as a JSON object on a single line.
        """
        if not tools:
            return ""

        tool_lines = []
        for tool in tools:
            schema = tool.to_openai_schema()
            tool_lines.append(json.dumps(schema, ensure_ascii=False))

        joined_tools = "\n".join(tool_lines)
        return f"<tools>\n{joined_tools}\n</tools>"

    @classmethod
    def format_tool_response(cls, tool_name: str, content: Any) -> str:
        """
        Format a tool execution result into Hermes <tool_response> XML.
        """
        payload = {
            "name": tool_name,
            "content": content,
        }
        json_str = json.dumps(payload, ensure_ascii=False)
        return f"<tool_response>\n{json_str}\n</tool_response>"

    @classmethod
    def parse_tool_calls_from_text(cls, text: str) -> List[Dict[str, Any]]:
        """
        Extract <tool_call> blocks from raw LLM text and parse JSON payloads.
        Returns a list of dictionaries with 'name' and 'arguments'.
        """
        if not text:
            return []

        calls: List[Dict[str, Any]] = []
        matches = cls.TOOL_CALL_REGEX.findall(text)

        for match in matches:
            match_str = match.strip()
            if not match_str:
                continue
            try:
                parsed = json.loads(match_str)
                if isinstance(parsed, dict) and "name" in parsed:
                    args = parsed.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {"raw_arguments": args}
                    calls.append({
                        "name": str(parsed["name"]),
                        "arguments": args if isinstance(args, dict) else {"value": args},
                    })
            except json.JSONDecodeError:
                # Try relaxed regex extraction for unquoted / malformed JSON
                name_match = re.search(r'"name"\s*:\s*"([^"]+)"', match_str)
                if name_match:
                    name = name_match.group(1)
                    calls.append({
                        "name": name,
                        "arguments": {"raw": match_str},
                    })

        return calls

    @classmethod
    def extract_scratchpad(cls, text: str) -> Tuple[Optional[str], str]:
        """
        Extract inner monologue / scratchpad from text and return (thought, clean_text).
        Removes <thought>, <scratch_pad>, <thinking>, and <tool_call> tags from clean_text.
        """
        if not text:
            return None, ""

        thoughts: List[str] = []
        for match in cls.THOUGHT_REGEX.findall(text):
            cleaned = match.strip()
            if cleaned:
                thoughts.append(cleaned)

        thought_content = "\n\n".join(thoughts) if thoughts else None

        # Clean text from thoughts and tool calls for final presentation
        clean_text = cls.THOUGHT_REGEX.sub("", text)
        clean_text = cls.TOOL_CALL_REGEX.sub("", clean_text)
        # Strip any unclosed tags
        clean_text = re.sub(r"</?(?:tool_call|tool_response|tools|thought|scratch_pad|thinking)>", "", clean_text)
        return thought_content, clean_text.strip()

    @classmethod
    def extract_thoughts_and_clean_text(cls, text: str) -> Tuple[str, Optional[str]]:
        """
        Extract inner monologue / scratchpad from text and return (clean_text, thought).
        """
        thought, clean_text = cls.extract_scratchpad(text)
        return clean_text, thought


class OpenHumanPrompts:
    """
    OpenHuman Persona and Prompt Assembly Engine.
    Combines companion persona, memory hierarchy, tools, and current temporal context.
    """

    BASE_SYSTEM_PROMPT = """You are an intelligent, empathetic, and proactive personal AI companion powered by OpenHuman and Hermes.
You operate continuously in the cloud and have direct access to the user's private Obsidian knowledge base.

# Core Principles
1. Privacy & Respect: The user's Obsidian vault is their private ground truth. Treat all notes as personal and confidential.
2. Direct & Concise: Provide clear, well-structured, human-like answers. Avoid unnecessary fluff, repetitive boilerplate, or unsolicited lectures.
3. Proactive Knowledge Integration: When relevant, consult notes, daily logs, project files, and wikilinks to ground your answers.
4. Safe Note Management: When writing notes, preserve existing content unless explicitly asked to overwrite. Append timestamped logs cleanly.
5. Structured Actions: Use available tools to search, read, write, or sync the vault whenever required.

# Temporal Grounding
- Current UTC Time: {current_time_utc}
- Local Context: Obsidian Vault Active
"""

    REFLEX_TRIAGE_PROMPT = """You are the fast Reflex Router for the OpenHuman companion.
Classify the following user message into one of these intent categories:
- COMMAND: Message starts with a slash command or is an administrative action (/note, /sync, /status, /help, /ask).
- QUICK_CHAT: Simple greeting, thanks, conversational small talk, or direct clarification that needs NO note lookup or modification.
- VAULT_READ: User is asking to look up information, retrieve past notes, check tasks, or search knowledge base.
- VAULT_WRITE: User is asking to create, update, append a note, log an event, or save information.
- DEEP_REASONING: Complex multi-step request, synthesis, project planning, or open-ended reasoning requiring agent loop.

Respond with ONLY a JSON object:
{"intent": "COMMAND" | "QUICK_CHAT" | "VAULT_READ" | "VAULT_WRITE" | "DEEP_REASONING", "reasoning": "brief explanation", "suggested_tool": "tool_name or null"}
"""

    @classmethod
    def build_system_prompt(
        cls,
        persona_instructions: Optional[str] = None,
        memory_context: Optional[str] = None,
        tools: Optional[List[ToolDefinition]] = None,
        user_name: str = "User",
        persona_name: Optional[str] = None,
        user_profile: Optional[str] = None,
        recent_notes: Optional[List[str]] = None,
    ) -> str:
        """
        Assemble complete system prompt for Hermes / OpenHuman agent.
        """
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        prompt_parts = [
            cls.BASE_SYSTEM_PROMPT.format(current_time_utc=now_str),
            f"\n# User Profile\n- User: {user_name}",
        ]

        if persona_name:
            prompt_parts.append(f"- Active Persona: {persona_name}")

        if user_profile:
            prompt_parts.append(f"- User Profile Notes: {user_profile}")

        if persona_instructions:
            prompt_parts.append(f"\n# Persona Guidelines\n{persona_instructions.strip()}")

        if recent_notes:
            notes_str = "\n".join(f"- [[{n}]]" if not n.startswith("[[") else f"- {n}" for n in recent_notes)
            prompt_parts.append(f"\n# Recent Obsidian Notes\n{notes_str}")

        if memory_context:
            prompt_parts.append(f"\n# Obsidian Memory Tree Context\n{memory_context.strip()}")

        if tools:
            tools_xml = HermesPrompts.format_tools_declaration(tools)
            prompt_parts.append(
                f"\n# Available Tools\nYou have access to tools to interact with the Obsidian knowledge base. "
                f"To call a tool, output a `<tool_call>` block with JSON arguments.\n\n{tools_xml}"
            )

        return "\n".join(prompt_parts)
