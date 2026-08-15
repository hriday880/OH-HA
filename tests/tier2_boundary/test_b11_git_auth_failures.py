"""
Boundary Test 11: Git Authentication Failures & Secret Scrubbing.
Tests invalid credentials, SSH CRLF normalization, unreachable remotes, and log token redaction.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from bot.git_sync.auth import GitAuthManager, scrub_git_credentials


class TestBoundary11GitAuthFailures:
    """Boundary tests for Feature 11 (Git Auth & Lifecycle)."""

    def test_crlf_ssh_key_normalization(self, tmp_path: Path):
        """Test SSH private key containing Windows CRLF line endings is converted to Unix LF."""
        crlf_key = "-----BEGIN OPENSSH PRIVATE KEY-----\r\nbody_line_1\r\nbody_line_2\r\n-----END OPENSSH PRIVATE KEY-----\r\n"
        auth = GitAuthManager(ssh_key=crlf_key)
        key_file = auth.setup_ssh_key_file(tmp_path)

        content = key_file.read_text(encoding="utf-8")
        assert "\r\n" not in content
        assert content.endswith("\n")

    def test_credential_scrubbing_multiple_urls_in_trace(self):
        """Test scrubbing multiple credentials from complex traceback logs."""
        log_snippet = """
        GitCommandError: Command 'git push https://ghp_secret_token_111@github.com/org/repo.git' failed.
        Additional context: cloned from https://alice:superpass999@gitlab.com/org/vault.git
        """
        scrubbed = scrub_git_credentials(log_snippet)
        assert "ghp_secret_token_111" not in scrubbed
        assert "superpass999" not in scrubbed
        assert "https://***:***@github.com/org/repo.git" in scrubbed
        assert "https://***:***@gitlab.com/org/vault.git" in scrubbed

    def test_ssh_key_setup_without_key_raises_error(self, tmp_path: Path):
        """Test calling setup_ssh_key_file without ssh_key raises ValueError."""
        auth = GitAuthManager(ssh_key=None)
        with pytest.raises(ValueError):
            auth.setup_ssh_key_file(tmp_path)

    def test_scrub_git_credentials_empty_string(self):
        """Test scrubbing empty string returns empty string."""
        assert scrub_git_credentials("") == ""

    def test_format_authenticated_url_non_https(self):
        """Test formatting non-HTTPS URLs (e.g. SSH git@...) returns original URL unchanged."""
        auth = GitAuthManager(auth_token="ghp_token")
        ssh_url = "git@github.com:user/vault.git"
        assert auth.format_authenticated_url(ssh_url) == ssh_url
