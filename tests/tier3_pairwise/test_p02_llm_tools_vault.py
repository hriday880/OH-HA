"""
Pairwise Test 2: LLM Tool Calling & Obsidian Vault Operations.
Tests multi-step Hermes reasoning reading, searching, and writing notes in the Obsidian knowledge base.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from bot.config import Config
from bot.agent.pipeline import SplitBrainAgentPipeline
from bot.agent.providers import MockLLMProvider
from bot.agent.tools import ToolDefinition, ToolRegistry
from bot.vault.manager import VaultManager
from bot.vault.search import VaultSearchEngine


class TestPairwiseLLMToolsVault:
    """Pairwise Integration Suite: LLM Tool Calling + Vault Manager."""

    @pytest.mark.asyncio
    async def test_llm_reads_note_and_synthesizes_answer(self, test_config: Config, mock_vault_dir: Path):
        """Test Hermes issuing read_note tool call, receiving note content, and producing synthesis."""
        vault = VaultManager(mock_vault_dir)
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="read_note", description="Read note", parameters={"type": "object", "properties": {"path": {"type": "string"}}}),
            lambda path: vault.read_note(path).raw_body,
        )

        llm = MockLLMProvider()
        # Step 1: Tool call
        llm.queue_tool_call("read_note", {"path": "40-projects/Project_Apollo.md"})
        # Step 2: Final answer
        llm.queue_text_response("Project Apollo is focused on autonomous cloud deployment.")

        pipeline = SplitBrainAgentPipeline(
            config=test_config,
            primary_provider=llm,
            tool_registry=registry,
        )

        result = await pipeline.process_message("What is Project Apollo about?")
        assert "Project Apollo is focused on" in result.content
        assert len(result.tools_executed) == 1
        assert result.tools_executed[0].name == "read_note"

    @pytest.mark.asyncio
    async def test_llm_writes_new_note_to_vault(self, test_config: Config, mock_vault_dir: Path):
        """Test Hermes issuing write_note tool call creating a new note on disk."""
        vault = VaultManager(mock_vault_dir)
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="write_note",
                description="Write note",
                parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
            ),
            lambda path, content, **kwargs: vault.write_note(path, content, mode="overwrite").path,
        )

        llm = MockLLMProvider()
        llm.queue_tool_call(
            "write_note",
            {"path": "50-knowledge/Microservices.md", "content": "# Microservices\n\nLoose coupling architecture."},
        )
        llm.queue_text_response("I have created the Microservices concept note for you.")

        pipeline = SplitBrainAgentPipeline(
            config=test_config,
            primary_provider=llm,
            tool_registry=registry,
        )

        result = await pipeline.process_message("Save a note on microservices")
        assert "created the Microservices concept note" in result.content
        assert (mock_vault_dir / "50-knowledge" / "Microservices.md").is_file()
        assert "Loose coupling" in (mock_vault_dir / "50-knowledge" / "Microservices.md").read_text()

    @pytest.mark.asyncio
    async def test_search_and_read_multi_step_workflow(self, test_config: Config, mock_vault_dir: Path):
        """Test multi-step search_notes -> read_note -> response sequence."""
        vault = VaultManager(mock_vault_dir)
        search_engine = VaultSearchEngine(mock_vault_dir)

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="search_notes", description="Search", parameters={"type": "object", "properties": {"query": {"type": "string"}}}),
            lambda query: search_engine.search(query),
        )
        registry.register(
            ToolDefinition(name="read_note", description="Read", parameters={"type": "object", "properties": {"path": {"type": "string"}}}),
            lambda path: vault.read_note(path).raw_body,
        )

        llm = MockLLMProvider()
        # Step 1: Search
        llm.queue_tool_call("search_notes", {"query": "Quantum"}, call_id="c1")
        # Step 2: Read
        llm.queue_tool_call("read_note", {"path": "50-knowledge/Quantum_Computing_Basics.md"}, call_id="c2")
        # Step 3: Synthesis
        llm.queue_text_response("Quantum computing uses qubits and entanglement.")

        pipeline = SplitBrainAgentPipeline(
            config=test_config,
            primary_provider=llm,
            tool_registry=registry,
        )

        result = await pipeline.process_message("What quantum physics concepts do I have saved?")
        assert "Quantum computing uses qubits" in result.content
        assert len(result.tools_executed) == 2
