"""
Boundary Test 5: Split-Brain Reflex Router & Extreme Inputs.
Tests giant inputs (>50k chars), symbols/emojis, empty prompts, and double provider failures.
"""

from __future__ import annotations

import pytest
from bot.config import Config
from bot.agent.pipeline import ReflexIntent, SplitBrainAgentPipeline
from bot.agent.providers import LLMProviderError, MockLLMProvider


class TestBoundary05SplitBrainEdgeCases:
    """Boundary tests for Feature 5 (Split-Brain Pipeline)."""

    def test_giant_prompt_intent_classification(self, test_config: Config):
        """Test classification of extremely large 50,000-character input."""
        pipeline = SplitBrainAgentPipeline(config=test_config)
        huge_text = "Discuss " + ("Quantum " * 5000)
        assert len(huge_text) > 40000

        intent = pipeline.classify_intent(huge_text)
        assert intent == ReflexIntent.DEEP_REASONING

    def test_symbols_and_emoji_only_input(self, test_config: Config):
        """Test input consisting only of emojis or punctuation."""
        pipeline = SplitBrainAgentPipeline(config=test_config)

        intent_emojis = pipeline.classify_intent("👋✨🎉🚀")
        assert intent_emojis in (ReflexIntent.QUICK_CHAT, ReflexIntent.DEEP_REASONING)

        intent_punct = pipeline.classify_intent("???!!!...")
        assert intent_punct in (ReflexIntent.QUICK_CHAT, ReflexIntent.DEEP_REASONING)

    @pytest.mark.asyncio
    async def test_both_primary_and_fallback_failure(self, test_config: Config):
        """Test graceful exception when both primary and fallback providers fail."""
        p1 = MockLLMProvider()
        p1.queue_response(LLMProviderError("Primary down"))

        p2 = MockLLMProvider()
        p2.queue_response(LLMProviderError("Fallback also down"))

        pipeline = SplitBrainAgentPipeline(
            config=test_config,
            primary_provider=p1,
            fallback_provider=p2,
        )

        with pytest.raises(LLMProviderError):
            await pipeline.process_message("Test failure across all providers")

    def test_whitespace_intent_classification(self, test_config: Config):
        """Test whitespace-only input."""
        pipeline = SplitBrainAgentPipeline(config=test_config)
        intent = pipeline.classify_intent("   \n\t  ")
        assert intent == ReflexIntent.QUICK_CHAT

    @pytest.mark.asyncio
    async def test_zero_step_protection(self, test_config: Config):
        """Test pipeline never enters infinite loop if provider keeps returning empty tool calls."""
        p = MockLLMProvider()
        p.queue_text_response("Clean single-turn response")

        pipeline = SplitBrainAgentPipeline(config=test_config, primary_provider=p)
        res = await pipeline.process_message("Hi")
        assert res.steps == 1
        assert res.content == "Clean single-turn response"
