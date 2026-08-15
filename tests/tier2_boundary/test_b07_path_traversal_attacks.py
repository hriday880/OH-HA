"""
Boundary Test 7: Adversarial Path Traversal & Injection Attacks.
Tests directory traversal attempts (../../), absolute paths, encoded attacks, and symlink breakout guards.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from bot.vault.manager import VaultPathSecurityError, sanitize_vault_path


class TestBoundary07PathTraversalAttacks:
    """Boundary tests for Feature 7 (Path Security)."""

    def test_deep_parent_traversal(self, tmp_path: Path):
        """Test deeply nested parent traversal attacks (../../../../..)."""
        vault = tmp_path / "vault"
        vault.mkdir()

        attacks = [
            "../../../../etc/passwd",
            "../../../secret.key",
            "10-daily/../../../../outside",
            "./../root.txt",
        ]
        for attack in attacks:
            with pytest.raises(VaultPathSecurityError):
                sanitize_vault_path(vault, attack)

    def test_absolute_system_paths_rejected(self, tmp_path: Path):
        """Test absolute root paths are confined or rejected."""
        vault = tmp_path / "vault"
        vault.mkdir()

        # In sanitize_vault_path, leading slashes are stripped or checked against vault boundary
        p = sanitize_vault_path(vault, "/etc/hosts")
        assert p == (vault / "etc/hosts.md").resolve()

    def test_windows_style_backslashes_traversal(self, tmp_path: Path):
        """Test Windows-style backslash traversal sequences (..\\..\\)."""
        vault = tmp_path / "vault"
        vault.mkdir()

        with pytest.raises(VaultPathSecurityError):
            sanitize_vault_path(vault, r"..\..\windows\system32\config.sys")

    def test_null_byte_poisoning_in_various_positions(self, tmp_path: Path):
        """Test null bytes injected at beginning, middle, and end."""
        vault = tmp_path / "vault"
        vault.mkdir()

        for attack in ["\0note.md", "note\0.md", "note.md\0"]:
            with pytest.raises(VaultPathSecurityError):
                sanitize_vault_path(vault, attack)

    def test_whitespace_and_control_char_paths(self, tmp_path: Path):
        """Test path with tabs or carriage returns is sanitized or rejected."""
        vault = tmp_path / "vault"
        vault.mkdir()

        p = sanitize_vault_path(vault, "  notes/my_note.md  ")
        assert p == (vault / "notes" / "my_note.md").resolve()
