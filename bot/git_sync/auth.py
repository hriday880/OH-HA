"""
Git Authentication and Credential Management.

Provides HTTPS Personal Access Token (PAT) formatting, SSH deploy key management
with strict 0600 file permissions, and regex-based credential scrubbing for logs and traces.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import re
import stat
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

# Regular expressions for identifying and redacting URL embedded credentials
# Matches https://<token>@ or https://<user>:<token>@
_CREDENTIAL_URL_REGEX = re.compile(r"(https?://)(?:[^@/\s:]+:[^@/\s]+|[^@/\s]+)@", re.IGNORECASE)


def scrub_git_credentials(text: Optional[str]) -> str:
    """
    Scrub tokens, passwords, and sensitive authentication strings from URLs in log messages or tracebacks.

    Examples:
        "https://ghp_secret@github.com/org/repo.git" -> "https://***:***@github.com/org/repo.git"
        "https://x-access-token:ghp_123@github.com/org/repo.git" -> "https://***:***@github.com/org/repo.git"
        "https://alice:secretpass@gitlab.com/org/repo.git" -> "https://***:***@gitlab.com/org/repo.git"
    """
    if not text:
        return ""

    return _CREDENTIAL_URL_REGEX.sub(r"\1***:***@", str(text))


class GitAuthManager:
    """
    Manages Git credentials, HTTPS Personal Access Tokens (PAT), and SSH deploy keys.
    """

    def __init__(
        self,
        auth_token: Optional[str] = None,
        ssh_key: Optional[str] = None,
        author_name: str = "OpenHuman Hermes Bot",
        author_email: str = "bot@openhuman.local",
    ) -> None:
        self.auth_token = auth_token.strip() if auth_token else None
        self.ssh_key = ssh_key
        self.author_name = author_name
        self.author_email = author_email
        self.ssh_key_path: Optional[Path] = None

    def format_authenticated_url(self, remote_url: str) -> str:
        """
        Format an HTTPS Git remote URL with embedded Personal Access Token (PAT).
        Non-HTTPS URLs (e.g., SSH `git@github.com:...`) are returned unchanged.
        """
        if not remote_url or not isinstance(remote_url, str):
            return ""

        trimmed_url = remote_url.strip()

        # If not HTTPS or no token provided, return original URL
        if not self.auth_token or not trimmed_url.startswith(("https://", "http://")):
            return trimmed_url

        scheme = "https://" if trimmed_url.startswith("https://") else "http://"
        # Strip existing credentials if present
        clean_url = re.sub(r"^https?://(?:[^@]+@)?", "", trimmed_url)

        return f"{scheme}x-access-token:{self.auth_token}@{clean_url}"

    def setup_ssh_key_file(
        self,
        target_dir: Union[str, Path],
        filename: str = "id_deploy_rsa",
    ) -> Path:
        """
        Write SSH private key string to a secure file with strict 0600 permissions.
        Normalizes Windows CRLF to Unix LF line endings.

        Raises:
            ValueError: If no SSH key is configured or key content is empty.
        """
        if not self.ssh_key or not self.ssh_key.strip():
            raise ValueError("No SSH key configured.")

        dir_path = Path(target_dir).resolve()
        dir_path.mkdir(parents=True, exist_ok=True)

        key_file = dir_path / filename

        # Normalize CRLF line endings to Unix LF and ensure trailing newline
        clean_key = self.ssh_key.strip().replace("\r\n", "\n").replace("\r", "\n") + "\n"

        # Write key content
        key_file.write_text(clean_key, encoding="utf-8")

        # Enforce strict 0600 permissions (read/write by owner only)
        os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)
        self.ssh_key_path = key_file

        return key_file

    def get_ssh_command(self, custom_key_path: Optional[Path] = None) -> str:
        """
        Build a secure GIT_SSH_COMMAND option string disabling interactive prompts
        and using the specified deploy key.
        """
        key = custom_key_path or self.ssh_key_path
        if key:
            key_str = str(key).replace("\\", "/")
            return f"ssh -i '{key_str}' -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
        return "ssh -o StrictHostKeyChecking=accept-new"

    def get_git_env(self, custom_ssh_key_path: Optional[Path] = None) -> Dict[str, str]:
        """
        Construct environment variable dictionary for subprocess Git executions.
        Injects author identity and SSH configuration without leaking secrets.
        """
        env = os.environ.copy()
        env["GIT_CONFIG_GLOBAL"] = "/dev/null"
        env["GIT_CONFIG_SYSTEM"] = "/dev/null"
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_AUTHOR_NAME"] = self.author_name
        env["GIT_AUTHOR_EMAIL"] = self.author_email
        env["GIT_COMMITTER_NAME"] = self.author_name
        env["GIT_COMMITTER_EMAIL"] = self.author_email
        env["GIT_TERMINAL_PROMPT"] = "0"

        key = custom_ssh_key_path or self.ssh_key_path
        if key:
            env["GIT_SSH_COMMAND"] = self.get_ssh_command(key)

        return env
