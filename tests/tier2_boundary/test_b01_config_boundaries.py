"""
Boundary Test 1: Configuration & Environment Boundaries.
Tests edge limits, invalid types, port boundaries (1-65535), and malformed JSON user lists.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from bot.config import Config


class TestBoundary01Config:
    """Boundary tests for Feature 1 (Configuration)."""

    def test_port_minimum_and_maximum_boundaries(self):
        """Test valid boundary ports (1, 65535) and invalid ports (0, 70000, -1)."""
        c_min = Config(port=1)
        assert c_min.port == 1

        c_max = Config(port=65535)
        assert c_max.port == 65535

        with pytest.raises(Exception):
            Config(port=0)

        with pytest.raises(Exception):
            Config(port=65536)

        with pytest.raises(Exception):
            Config(port=-80)

    def test_malformed_json_user_whitelist_graceful_recovery(self):
        """Test malformed JSON string for allowed_telegram_user_ids does not crash config."""
        c = Config(allowed_telegram_user_ids="[123, unquoted_bad_json]")  # type: ignore
        assert isinstance(c.allowed_telegram_user_ids, list)

    def test_max_reasoning_steps_boundaries(self):
        """Test min (1) and max (20) reasoning steps boundaries."""
        c1 = Config(max_reasoning_steps=1)
        assert c1.max_reasoning_steps == 1

        c20 = Config(max_reasoning_steps=20)
        assert c20.max_reasoning_steps == 20

        with pytest.raises(Exception):
            Config(max_reasoning_steps=0)

        with pytest.raises(Exception):
            Config(max_reasoning_steps=25)

    def test_temperature_exact_boundaries(self):
        """Test exact limits 0.0 and 2.0 for LLM temperature."""
        c0 = Config(llm_temperature=0.0)
        assert c0.llm_temperature == 0.0

        c2 = Config(llm_temperature=2.0)
        assert c2.llm_temperature == 2.0

        with pytest.raises(Exception):
            Config(llm_temperature=2.01)

    def test_auto_sync_interval_zero_disables_sync(self):
        """Test auto_sync_interval_seconds=0 is accepted to disable auto-sync."""
        c = Config(auto_sync_interval_seconds=0)
        assert c.auto_sync_interval_seconds == 0
