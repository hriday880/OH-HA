"""
OpenHuman & Hermes Agent Subsystem.

Contains LLM provider adapters, Hermes 3 ChatML XML tool prompt generation,
Tool registry & dispatcher, OpenHuman persona & memory tree builder,
and the Split-Brain reflex/reasoning agent pipeline.
"""

from bot.agent.prompts import HermesPrompts, OpenHumanPrompts
from bot.agent.tools import (
    ToolCall,
    ToolDefinition,
    ToolExecutionError,
    ToolRegistry,
    ToolResult,
)
from bot.agent.providers import (
    BaseLLMProvider,
    LLMResponse,
    MockLLMProvider,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
    GroqProvider,
    TogetherProvider,
    create_llm_provider,
)
from bot.agent.persona import MemoryTreeContext, OpenHumanPersona
from bot.agent.pipeline import PipelineResult, ReflexIntent, SplitBrainAgentPipeline

__all__ = [
    "HermesPrompts",
    "OpenHumanPrompts",
    "ToolCall",
    "ToolDefinition",
    "ToolExecutionError",
    "ToolRegistry",
    "ToolResult",
    "BaseLLMProvider",
    "LLMResponse",
    "MockLLMProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
    "GroqProvider",
    "TogetherProvider",
    "create_llm_provider",
    "MemoryTreeContext",
    "OpenHumanPersona",
    "PipelineResult",
    "ReflexIntent",
    "SplitBrainAgentPipeline",
]
