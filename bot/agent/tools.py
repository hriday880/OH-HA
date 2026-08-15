"""
Tool Definitions, Schemas, and Execution Dispatcher.

Defines ToolDefinition, ToolCall, ToolResult, and ToolRegistry for registering
and executing tool calls from Hermes / LLM with robust error handling and path validation.
"""

from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""
    pass


@dataclass
class ToolDefinition:
    """Definition of an agent tool matching OpenAI/Hermes tool calling schema."""
    name: str
    description: str
    parameters: Dict[str, Any]

    def to_openai_schema(self) -> Dict[str, Any]:
        """Format as an OpenAI-compatible function definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class ToolCall:
    """Represents a tool call requested by the LLM."""
    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ToolCall:
        call_id = data.get("id", f"call_{data.get('name', 'tool')}")
        name = data.get("name", "")
        args = data.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {"raw_arguments": args}
        return cls(id=str(call_id), name=str(name), arguments=args)


@dataclass
class ToolResult:
    """Result of a tool execution."""
    tool_call_id: str
    name: str
    result: Any
    is_error: bool = False
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        if self.is_error:
            return {
                "status": "error",
                "tool": self.name,
                "error": self.error_message or "Unknown tool error",
            }
        return {
            "status": "success",
            "tool": self.name,
            "data": self.result,
        }

    def to_content_str(self) -> str:
        """Serialize tool result to JSON or string for LLM response injection."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


# Standard Obsidian Vault Tool Schemas
STANDARD_OBSIDIAN_TOOLS: List[ToolDefinition] = [
    ToolDefinition(
        name="read_note",
        description="Read markdown content and frontmatter from an Obsidian note in the vault.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to note, e.g. 'Daily/2026-08-14.md' or 'Projects/Agent.md'",
                },
                "section": {
                    "type": "string",
                    "description": "Optional heading/section to extract specifically",
                },
            },
            "required": ["path"],
        },
    ),
    ToolDefinition(
        name="write_note",
        description="Create, overwrite, append, or prepend markdown content to an Obsidian note in the vault.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to note, e.g. 'Daily/2026-08-14.md'",
                },
                "content": {
                    "type": "string",
                    "description": "Markdown formatted content to write",
                },
                "mode": {
                    "type": "string",
                    "enum": ["append", "prepend", "overwrite"],
                    "description": "Write mode ('append' adds to bottom, 'prepend' adds below frontmatter, 'overwrite' replaces)",
                },
            },
            "required": ["path", "content"],
        },
    ),
    ToolDefinition(
        name="search_notes",
        description="Search notes across the Obsidian vault by keyword, phrase, or tag.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword or text",
                },
                "tag": {
                    "type": "string",
                    "description": "Optional tag filter without '#' e.g. 'project'",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 10)",
                },
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="list_notes",
        description="List notes in a folder or list all directories in the Obsidian vault.",
        parameters={
            "type": "object",
            "properties": {
                "folder": {
                    "type": "string",
                    "description": "Subdirectory to inspect. Pass empty string '' for root folder.",
                },
            },
        },
    ),
    ToolDefinition(
        name="sync_vault",
        description="Synchronize the local Obsidian vault with the remote Git repository.",
        parameters={
            "type": "object",
            "properties": {
                "commit_message": {
                    "type": "string",
                    "description": "Optional Git commit message summary",
                },
            },
        },
    ),
]


class ToolRegistry:
    """
    Registry for managing and executing tools available to the LLM.
    Supports both synchronous and asynchronous handlers.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable[..., Any]] = {}

    def register(
        self,
        definition: ToolDefinition,
        handler: Callable[..., Any],
    ) -> None:
        """Register a tool with its schema definition and callable execution handler."""
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler
        logger.debug(f"Registered tool: {definition.name}")

    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        self._tools.pop(name, None)
        self._handlers.pop(name, None)

    def get_definitions(self) -> List[ToolDefinition]:
        """Return list of all registered tool definitions."""
        return list(self._tools.values())

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Return list of tool definitions formatted for OpenAI API."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._handlers

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call and return a structured ToolResult.
        Catches all runtime errors and returns them safely inside the result object.
        """
        name = tool_call.name
        if name not in self._handlers:
            err_msg = f"Unknown tool: '{name}'. Available tools: {list(self._tools.keys())}"
            logger.warning(err_msg)
            return ToolResult(
                tool_call_id=tool_call.id,
                name=name,
                result=None,
                is_error=True,
                error_message=err_msg,
            )

        handler = self._handlers[name]
        kwargs = tool_call.arguments or {}

        try:
            # Check handler signature to prevent unexpected keyword argument errors
            sig = inspect.signature(handler)
            accepts_var_kw = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            )
            if not accepts_var_kw:
                valid_keys = set(sig.parameters.keys())
                filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_keys}
            else:
                filtered_kwargs = kwargs

            if inspect.iscoroutinefunction(handler):
                result = await handler(**filtered_kwargs)
            else:
                result = handler(**filtered_kwargs)

            # If result is an object with to_dict or model_dump, convert it
            if hasattr(result, "to_dict") and callable(result.to_dict):
                result_data = result.to_dict()
            elif hasattr(result, "model_dump") and callable(result.model_dump):
                result_data = result.model_dump()
            else:
                result_data = result

            return ToolResult(
                tool_call_id=tool_call.id,
                name=name,
                result=result_data,
                is_error=False,
            )
        except Exception as e:
            logger.error(f"Error executing tool '{name}' with args {kwargs}: {e}", exc_info=True)
            return ToolResult(
                tool_call_id=tool_call.id,
                name=name,
                result=None,
                is_error=True,
                error_message=f"ToolExecutionError: {type(e).__name__} - {str(e)}",
            )
