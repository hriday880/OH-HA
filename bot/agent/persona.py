"""
OpenHuman Persona Management and Memory Tree Context Builder.

Maps the Obsidian Markdown Vault hierarchy (Profile.md, Daily/, Projects/, People/, Knowledge/)
into a token-budgeted memory context for system prompt injection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MemoryTreeContext:
    """
    Builds context summaries from Obsidian vault folder structure.
    Hierarchically organizes Profile, Daily notes, Projects, and Knowledge.
    """

    vault_path: Path = field(default_factory=lambda: Path("./vault"))
    max_context_chars: int = 4000

    def scan_profile(self) -> Optional[str]:
        """Read user profile and preferences from Profile.md or User.md if present."""
        for candidate in ("Profile.md", "profile.md", "User.md", "user.md", "About.md"):
            p = self.vault_path / candidate
            if p.is_file():
                try:
                    content = p.read_text(encoding="utf-8").strip()
                    if content:
                        # Limit profile snippet to first 1000 chars
                        return content[:1000]
                except Exception as e:
                    logger.debug(f"Error reading profile file {p}: {e}")
        return None

    def scan_recent_daily_notes(self, count: int = 2) -> List[Dict[str, str]]:
        """Retrieve recent daily note snippets from Daily/ folder."""
        daily_dir = self.vault_path / "Daily"
        if not daily_dir.is_dir():
            daily_dir = self.vault_path / "daily"
            if not daily_dir.is_dir():
                return []

        daily_files = sorted(
            [f for f in daily_dir.glob("*.md") if f.is_file()],
            key=lambda f: f.name,
            reverse=True,
        )

        results: List[Dict[str, str]] = []
        for file_path in daily_files[:count]:
            try:
                content = file_path.read_text(encoding="utf-8").strip()
                if content:
                    # Take first 600 chars of daily note
                    snippet = content[:600]
                    results.append({"filename": file_path.name, "snippet": snippet})
            except Exception as e:
                logger.debug(f"Error reading daily note {file_path}: {e}")

        return results

    def scan_active_projects(self, max_projects: int = 3) -> List[Dict[str, str]]:
        """Scan active project outlines from Projects/ folder."""
        proj_dir = self.vault_path / "Projects"
        if not proj_dir.is_dir():
            proj_dir = self.vault_path / "projects"
            if not proj_dir.is_dir():
                return []

        proj_files = sorted(
            [f for f in proj_dir.glob("*.md") if f.is_file()],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        results: List[Dict[str, str]] = []
        for file_path in proj_files[:max_projects]:
            try:
                content = file_path.read_text(encoding="utf-8").strip()
                if content:
                    results.append({"title": file_path.stem, "snippet": content[:500]})
            except Exception as e:
                logger.debug(f"Error reading project note {file_path}: {e}")

        return results

    def list_memory_folders(self) -> List[str]:
        """List active memory categories found in vault."""
        if not self.vault_path.is_dir():
            return []
        return [
            d.name
            for d in self.vault_path.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    def build_context_block(self) -> str:
        """
        Assemble comprehensive memory tree context block respecting char budget.
        """
        sections: List[str] = []
        chars_used = 0

        # 1. Profile
        profile = self.scan_profile()
        if profile:
            sec = f"### User Profile & Preferences\n{profile}"
            sections.append(sec)
            chars_used += len(sec)

        # 2. Recent Daily Notes
        daily_notes = self.scan_recent_daily_notes(count=2)
        if daily_notes:
            daily_lines = ["### Recent Daily Activity (Episodic Memory)"]
            for note in daily_notes:
                daily_lines.append(f"**{note['filename']}**:\n{note['snippet']}")
            sec = "\n".join(daily_lines)
            if chars_used + len(sec) <= self.max_context_chars:
                sections.append(sec)
                chars_used += len(sec)

        # 3. Active Projects
        projects = self.scan_active_projects(max_projects=3)
        if projects:
            proj_lines = ["### Active Projects (Working Memory)"]
            for proj in projects:
                proj_lines.append(f"**Project: {proj['title']}**:\n{proj['snippet']}")
            sec = "\n".join(proj_lines)
            if chars_used + len(sec) <= self.max_context_chars:
                sections.append(sec)
                chars_used += len(sec)

        # 4. Vault structure overview
        folders = self.list_memory_folders()
        if folders:
            sec = f"### Vault Memory Structure\nAvailable Categories: {', '.join(folders)}"
            if chars_used + len(sec) <= self.max_context_chars:
                sections.append(sec)

        if not sections:
            return "No prior memory notes found in Obsidian vault. Fresh memory workspace."

        return "\n\n".join(sections)


@dataclass
class OpenHumanPersona:
    """
    OpenHuman Companion Persona configuration and greeting generator.
    """

    bot_name: str = "OpenHuman"
    user_name: str = "Friend"
    tone: str = "empathetic, concise, proactive, intellectual"
    custom_instructions: Optional[str] = None
    timezone: str = "UTC"

    def get_greeting(self, is_first_time: bool = False) -> str:
        """Generate welcoming persona greeting."""
        if is_first_time:
            return (
                f"👋 Hello {self.user_name}! I am **{self.bot_name}**, your personal AI companion.\n\n"
                f"I'm connected to your Obsidian knowledge base and ready to help you capture ideas, "
                f"search notes, organize projects, and reason through complex problems.\n\n"
                f"Use `/help` to view available commands or simply message me anything."
            )
        return (
            f"Hello {self.user_name}! What are we focusing on today? "
            f"I'm here to assist with your notes, projects, and questions."
        )

    def get_instructions_text(self) -> str:
        """Format persona instructions for system prompt."""
        parts = [
            f"- Companion Name: {self.bot_name}",
            f"- Preferred User Name: {self.user_name}",
            f"- Tone & Style: {self.tone}",
            f"- System Timezone: {self.timezone}",
        ]
        if self.custom_instructions:
            parts.append(f"- Custom Persona Directives: {self.custom_instructions}")
        return "\n".join(parts)
