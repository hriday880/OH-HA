"""
Tier 1 Feature Tests: Feature 1 - Configuration & Environment Validation.
"""

import os
import unittest
from pathlib import Path

from bot.config import Config, load_config, mask_secret


class TestConfigFeature(unittest.TestCase):
    """Tier 1 Unit tests for configuration loading, validation, and secret masking."""

    def test_default_configuration_values(self):
        """Test default values for standard cloud container deployment."""
        config = Config()
        self.assertEqual(config.llm_provider, "openrouter")
        self.assertEqual(config.llm_model, "nousresearch/hermes-3-llama-3.1-8b")
        self.assertEqual(config.port, 8080)
        self.assertEqual(config.host, "0.0.0.0")
        self.assertEqual(config.log_level, "INFO")
        self.assertEqual(config.environment, "development")
        self.assertEqual(config.max_reasoning_steps, 5)
        self.assertEqual(config.vault_path, Path("./vault"))

    def test_parse_allowed_user_ids_comma_string(self):
        """Test parsing comma-separated allowed user IDs."""
        config = Config(allowed_telegram_user_ids="12345, 67890, 99999")
        self.assertEqual(config.allowed_telegram_user_ids, [12345, 67890, 99999])
        self.assertTrue(config.is_user_allowed(12345))
        self.assertTrue(config.is_user_allowed(67890))
        self.assertFalse(config.is_user_allowed(11111))

    def test_parse_allowed_user_ids_json_list(self):
        """Test parsing JSON array string for user IDs."""
        config = Config(allowed_telegram_user_ids="[101, 202, 303]")
        self.assertEqual(config.allowed_telegram_user_ids, [101, 202, 303])
        self.assertTrue(config.is_user_allowed(101))

    def test_secret_masking(self):
        """Test secret masking in to_safe_dict and mask_secret."""
        token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        masked = mask_secret(token, show_prefix=4, show_suffix=4)
        self.assertTrue(masked.startswith("1234***ew11"))
        self.assertNotIn("ABC-DEF1234", masked)

        config = Config(
            telegram_bot_token=token,
            llm_api_key="sk-or-v1-supersecretkey123456789",
            git_auth_token="ghp_verysecretgittoken987654321",
        )
        safe_dict = config.mask_secrets()
        self.assertNotIn("ABC-DEF", safe_dict["telegram_bot_token"])
        self.assertNotIn("supersecretkey", safe_dict["llm_api_key"])
        self.assertNotIn("verysecretgittoken", safe_dict["git_auth_token"])

    def test_production_validation_catches_missing_token(self):
        """Test fail-fast validation in production mode when tokens are missing."""
        config = Config(environment="production", telegram_bot_token=None, allowed_telegram_user_ids=[])
        errors = config.validate_for_production()
        self.assertGreaterEqual(len(errors), 2)
        self.assertTrue(any("TELEGRAM_BOT_TOKEN" in e for e in errors))
        self.assertTrue(any("ALLOWED_TELEGRAM_USER_IDS" in e for e in errors))

    def test_environment_variable_loading(self):
        """Test loading configuration from environment variables."""
        old_env = os.environ.get("LLM_PROVIDER")
        try:
            os.environ["LLM_PROVIDER"] = "groq"
            os.environ["LLM_MODEL"] = "llama-3.1-70b-versatile"
            config = load_config()
            self.assertEqual(config.llm_provider, "groq")
            self.assertEqual(config.llm_model, "llama-3.1-70b-versatile")
        finally:
            if old_env is not None:
                os.environ["LLM_PROVIDER"] = old_env
            else:
                os.environ.pop("LLM_PROVIDER", None)
            os.environ.pop("LLM_MODEL", None)


if __name__ == "__main__":
    unittest.main()
