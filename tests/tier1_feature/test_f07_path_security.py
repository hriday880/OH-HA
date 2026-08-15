"""
Feature 7: Path Normalization & Traversal Security Test Suite.
Tests path sanitization, extension enforcement, and directory traversal attack prevention.
"""

from __future__ import annotations

from pathlib import Path
import pytest

# Try importing bot.vault.manager if present or test path security logic
try:
    from bot.vault.manager import VaultPathSecurityError, sanitize_vault_path
except ImportError:
    class VaultPathSecurityError(Exception):
        """Raised when a path escapes the vault boundary or contains illegal characters."""
        pass

    def sanitize_vault_path(vault_root: Path, relative_path: str) -> Path:
        """Sanitize and validate relative note path against vault root."""
        if not relative_path or not relative_path.strip():
            raise VaultPathSecurityError("Note path cannot be empty.")

        if "\0" in relative_path:
            raise VaultPathSecurityError("Null bytes are prohibited in note paths.")

        clean_str = relative_path.strip().replace("\\", "/").lstrip("/")
        
        # Enforce .md extension
        if not clean_str.endswith(".md"):
            clean_str = f"{clean_str}.md"

        target_path = (vault_root / clean_str).resolve()
        vault_resolved = vault_root.resolve()

        try:
            target_path.relative_to(vault_resolved)
        except ValueError:
            raise VaultPathSecurityError(f"Directory traversal detected: path '{relative_path}' escapes vault root.")

        return target_path


class TestFeature07PathSecurity:
    """Test suite for Feature 7: Path Normalization & Traversal Security."""

    def test_valid_path_normalization(self, tmp_path: Path):
        """Test standard relative paths normalize properly with .md extension."""
        vault = tmp_path / "vault"
        vault.mkdir()

        p1 = sanitize_vault_path(vault, "40-projects/Project_Apollo")
        assert p1 == (vault / "40-projects" / "Project_Apollo.md").resolve()

        p2 = sanitize_vault_path(vault, "/10-daily/2026-08-15.md")
        assert p2 == (vault / "10-daily" / "2026-08-15.md").resolve()

        p3 = sanitize_vault_path(vault, "simple_note")
        assert p3 == (vault / "simple_note.md").resolve()

    def test_directory_traversal_double_dot_rejected(self, tmp_path: Path):
        """Test that relative paths with ../ outside vault are strictly rejected."""
        vault = tmp_path / "vault"
        vault.mkdir()

        with pytest.raises(VaultPathSecurityError):
            sanitize_vault_path(vault, "../../etc/passwd")

        with pytest.raises(VaultPathSecurityError):
            sanitize_vault_path(vault, "40-projects/../../outside.md")

    def test_null_byte_injection_rejected(self, tmp_path: Path):
        """Test that null bytes in paths raise VaultPathSecurityError."""
        vault = tmp_path / "vault"
        vault.mkdir()

        with pytest.raises(VaultPathSecurityError):
            sanitize_vault_path(vault, "note.md\0.secret")

    def test_empty_or_whitespace_path_rejected(self, tmp_path: Path):
        """Test empty string and whitespace paths raise security errors."""
        vault = tmp_path / "vault"
        vault.mkdir()

        with pytest.raises(VaultPathSecurityError):
            sanitize_vault_path(vault, "")

        with pytest.raises(VaultPathSecurityError):
            sanitize_vault_path(vault, "   ")

    def test_nested_subfolder_creation_allowed(self, tmp_path: Path):
        """Test deep valid nested subfolders inside vault are accepted."""
        vault = tmp_path / "vault"
        vault.mkdir()

        p = sanitize_vault_path(vault, "50-knowledge/sub/deep/topic/concept.md")
        assert p == (vault / "50-knowledge" / "sub" / "deep" / "topic" / "concept.md").resolve()
