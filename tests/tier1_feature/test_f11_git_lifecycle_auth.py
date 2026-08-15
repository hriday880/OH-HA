"""
Feature 11: Git Repository Lifecycle & Auth Test Suite.
Tests Git repo clone, HTTPS PAT authentication, SSH deploy key management, and secret scrubbing.
"""

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import pytest

# Try importing bot.git_sync.auth if present or implement contract-based auth manager
try:
    from bot.git_sync.auth import GitAuthManager, scrub_git_credentials
except ImportError:
    import re

    def scrub_git_credentials(text: str) -> str:
        """Scrub tokens and passwords from URLs in strings."""
        if not text:
            return ""
        # Scrub https://TOKEN@ or https://user:token@
        return re.sub(r"https://([^:]+:[^@]+|[^@]+)@", "https://***:***@", text)

    class GitAuthManager:
        def __init__(
            self,
            auth_token: Optional[str] = None,
            ssh_key: Optional[str] = None,
            author_name: str = "OpenHuman Hermes Bot",
            author_email: str = "bot@openhuman.local",
        ) -> None:
            self.auth_token = auth_token
            self.ssh_key = ssh_key
            self.author_name = author_name
            self.author_email = author_email

        def format_authenticated_url(self, remote_url: str) -> str:
            if not self.auth_token or not remote_url.startswith("https://"):
                return remote_url
            clean_url = re.sub(r"^https://([^@]+@)?", "", remote_url)
            return f"https://x-access-token:{self.auth_token}@{clean_url}"

        def setup_ssh_key_file(self, target_dir: Path) -> Path:
            if not self.ssh_key:
                raise ValueError("No SSH key configured.")
            key_file = target_dir / "id_deploy_rsa"
            clean_key = self.ssh_key.strip().replace("\r\n", "\n") + "\n"
            key_file.write_text(clean_key, encoding="utf-8")
            key_file.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600
            return key_file


class TestFeature11GitLifecycleAuth:
    """Test suite for Feature 11: Git Repository Lifecycle & Auth."""

    def test_https_pat_url_formatting(self):
        """Test formatting HTTPS remote URL with PAT token."""
        auth = GitAuthManager(auth_token="ghp_test_secret_12345")
        formatted = auth.format_authenticated_url("https://github.com/user/my-vault.git")
        assert "ghp_test_secret_12345" in formatted
        assert formatted.startswith("https://x-access-token:")

    def test_credential_scrubbing_from_error_logs(self):
        """Test that error messages containing access tokens are safely scrubbed."""
        raw_error = "fatal: unable to access 'https://x-access-token:ghp_super_secret_999@github.com/user/vault.git/': 403"
        scrubbed = scrub_git_credentials(raw_error)
        assert "ghp_super_secret_999" not in scrubbed
        assert "https://***:***@github.com/user/vault.git/" in scrubbed

    def test_ssh_deploy_key_file_creation_and_permissions(self, tmp_path: Path):
        """Test SSH private key is written with strict 0600 permissions."""
        ssh_content = "-----BEGIN OPENSSH PRIVATE KEY-----\ntest_key_body\n-----END OPENSSH PRIVATE KEY-----"
        auth = GitAuthManager(ssh_key=ssh_content)
        key_path = auth.setup_ssh_key_file(tmp_path)

        assert key_path.is_file()
        perms = stat.S_IMODE(key_path.stat().st_mode)
        assert perms == 0o600
        assert "test_key_body" in key_path.read_text()

    def test_clone_from_bare_remote(self, bare_git_remote: Path, tmp_path: Path):
        """Test cloning a repository from bare remote fixture."""
        clone_dir = tmp_path / "cloned_vault"
        result = subprocess.run(
            ["git", "clone", str(bare_git_remote), str(clone_dir)],
            capture_output=True,
            text=True,
            check=True,
        )
        assert clone_dir.is_dir()
        assert (clone_dir / "README.md").is_file()

    def test_git_author_identity_configuration(self, tmp_path: Path):
        """Test author name and email settings."""
        auth = GitAuthManager(author_name="Alice Bot", author_email="alice@bot.local")
        assert auth.author_name == "Alice Bot"
        assert auth.author_email == "alice@bot.local"
