"""
Pairwise Test 5: OpenHuman Memory Context & Search Synthesis.
Tests grounding Hermes reasoning with user profile memory and SQLite search index retrieval.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from bot.config import Config
from bot.agent.persona import MemoryTreeContext, OpenHumanPersona
from bot.agent.pipeline import SplitBrainAgentPipeline
from bot.agent.providers import MockLLMProvider
from bot.agent.tools import ToolDefinition, ToolRegistry
from bot.vault.search import VaultSearchEngine


class TestPairwiseSearchPersonaSynthesis:
    """Pairwise Integration Suite: Persona Memory + SQLite Search."""

    @pytest.mark.asyncio
    async def test_persona_and_search_grounding(self, test_config: Config, mock_vault_dir: Path):
        """Test agent using user persona directives and search tool to answer user question."""
        persona = OpenHumanPersona(bot_name="Atlas", user_name="Alice", tone="concise")
        memory_ctx = MemoryTreeContext(vault_path=mock_vault_dir)
        search_engine = VaultSearchEngine(mock_vault_dir)

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="search_notes", description="Search", parameters={"type": "object", "properties": {"query": {"type": "string"}}}),
            lambda query: search_engine.search(query),
        )

        llm = MockLLMProvider()
        llm.queue_tool_call("search_notes", {"query": "Apollo"})
        llm.queue_text_response("Alice, Project Apollo is your active companion deployment project.")

        pipeline = SplitBrainAgentPipeline(
            config=test_config,
            primary_provider=llm,
            tool_registry=registry,
            persona=persona,
            memory_context=memory_ctx,
        )

        result = await pipeline.process_message("What is my primary active project?")
        assert "Alice, Project Apollo is your active companion" in result.content
        assert len(result.tools_executed) == 1
