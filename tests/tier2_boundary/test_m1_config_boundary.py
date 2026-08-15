"""
Tier 2 Boundary Tests: Feature 1 - Configuration & Environment Validation.
"""

import unittest
from pathlib import Path
from pydantic import ValidationError

from bot.config import Config, mask_secret


class TestConfigBoundary(unittest.TestCase):
    """Tier 2 Boundary and Edge-case tests for configuration."""

    def test_empty_and_whitespace_user_ids(self):
        """Test parsing empty string or whitespace user IDs."""
        config1 = Config(allowed_telegram_user_ids="")
        self.assertEqual(config1.allowed_telegram_user_ids, [])

        config2 = Config(allowed_telegram_user_ids="   ")
        self.assertEqual(config2.allowed_telegram_user_ids, [])

    def test_malformed_user_ids_skips_invalid(self):
        """Test that malformed/non-integer user IDs are safely skipped."""
        config = Config(allowed_telegram_user_ids="12345, notanid, 67890, invalid!, 99999")
        self.assertEqual(config.allowed_telegram_user_ids, [12345, 67890, 99999])

    def test_single_integer_user_id(self):
        """Test passing single integer as user ID."""
        config = Config(allowed_telegram_user_ids=12345678)
        self.assertEqual(config.allowed_telegram_user_ids, [12345678])

    def test_temperature_boundary_values(self):
        """Test temperature limits (0.0 to 2.0)."""
        config_min = Config(llm_temperature=0.0)
        self.assertEqual(config_min.llm_temperature, 0.0)

        config_max = Config(llm_temperature=2.0)
        self.assertEqual(config_max.llm_temperature, 2.0)

        with self.assertRaises(ValidationError):
            Config(llm_temperature=-0.1)

        with self.assertRaises(ValidationError):
            Config(llm_temperature=2.1)

    def test_port_boundary_values(self):
        """Test valid port range boundaries."""
        config_low = Config(port=1)
        self.assertEqual(config_low.port, 1)

        config_high = Config(port=65535)
        self.assertEqual(config_high.port, 65535)

        with self.assertRaises(ValidationError):
            Config(port=0)

        with self.assertRaises(ValidationError):
            Config(port=65536)

    def test_mask_secret_edge_cases(self):
        """Test mask_secret with None, empty string, very short string."""
        self.assertEqual(mask_secret(None), "[NOT SET]")
        self.assertEqual(mask_secret(""), "[NOT SET]")
        self.assertEqual(mask_secret("123"), "***")
        self.assertEqual(mask_secret("short"), "***")


if __name__ == "__main__":
    unittest.main()
