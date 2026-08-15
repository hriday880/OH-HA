"""
Feature 1: Configuration & Environment Validation Test Suite.
Tests typed settings loading, fail-fast env validation, secret masking, and user whitelist parsing.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from bot.config import Config, mask_secret


class TestFeature01Config:
    """Test suite for Feature 1: Configuration and Environment Validation."""

    def test_default_config_instantiation(self, tmp_path: Path):
        """Test default values and types for clean config initialization."""
        config = Config(vault_path=tmp_path / "test_vault")
        assert config.llm_provider == "openrouter"
        assert config.llm_model == "nousresearch/hermes-3-llama-3.1-8b"
        assert config.llm_temperature == 0.7
        assert config.llm_max_tokens == 1024
        assert config.port == 8080
        assert config.host == "0.0.0.0"
        assert config.git_branch == "main"
        assert config.auto_sync_interval_seconds == 1800
        assert isinstance(config.vault_path, Path)

    def test_whitelist_parsing_variations(self):
        """Test parsing of user IDs from comma-separated string, JSON array, and ints."""
        # Comma-separated string
        c1 = Config(allowed_telegram_user_ids="12345, 67890, 111213")  # type: ignore
        assert c1.allowed_telegram_user_ids == [12345, 67890, 111213]

        # JSON array string
        c2 = Config(allowed_telegram_user_ids="[999, 888, 777]")  # type: ignore
        assert c2.allowed_telegram_user_ids == [999, 888, 777]

        # Single integer
        c3 = Config(allowed_telegram_user_ids=42)  # type: ignore
        assert c3.allowed_telegram_user_ids == [42]

        # Empty / None
        c4 = Config(allowed_telegram_user_ids="")  # type: ignore
        assert c4.allowed_telegram_user_ids == []

    def test_secret_masking_integrity(self):
        """Test secret masking preserves security and hides sensitive credentials in logs."""
        assert mask_secret(None) == "[NOT SET]"
        assert mask_secret("") == "[NOT SET]"
        assert mask_secret("short") == "***"
        assert mask_secret("sk-or-v1-abcdef1234567890abcdef") == "sk-***def"

        config = Config(
            telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            llm_api_key="sk-test-secret-key-super-confidential",
            git_auth_token="ghp_1234567890abcdefghijklmnopqrstuvwxyz",
        )
        masked = config.get_masked_dict()
        assert masked["telegram_bot_token"] != config.telegram_bot_token
        assert "super-confidential" not in masked["llm_api_key"]
        assert "ghp_" in masked["git_auth_token"]
        assert "***" in masked["git_auth_token"]

    def test_fail_fast_validation_temperature_and_tokens(self):
        """Test that invalid temperature or tokens fail validation immediately."""
        with pytest.raises(Exception):
            Config(llm_temperature=3.5)  # Max is 2.0

        with pytest.raises(Exception):
            Config(llm_temperature=-0.5)  # Min is 0.0

        with pytest.raises(Exception):
            Config(llm_max_tokens=-10)  # Must be > 0

    def test_env_var_loading_and_override(self, monkeypatch, tmp_path: Path):
        """Test that environment variables correctly override default configurations."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env_bot_token_999")
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setenv("LLM_MODEL", "llama-3.1-70b-versatile")
        monkeypatch.setenv("PORT", "9090")
        monkeypatch.setenv("ALLOWED_TELEGRAM_USER_IDS", "1001,1002")

        cfg = Config(vault_path=tmp_path)
        assert cfg.telegram_bot_token == "env_bot_token_999"
        assert cfg.llm_provider == "groq"
        assert cfg.llm_model == "llama-3.1-70b-versatile"
        assert cfg.port == 9090
        assert cfg.allowed_telegram_user_ids == [1001, 1002]

    def test_vault_path_expansion_and_resolution(self, tmp_path: Path):
        """Test vault path converts string paths to resolved Path objects."""
        target = tmp_path / "custom_vault"
        cfg = Config(vault_path=str(target))
        assert isinstance(cfg.vault_path, Path)
        assert cfg.vault_path == target
