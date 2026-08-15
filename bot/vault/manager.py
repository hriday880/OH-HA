"""
Obsidian Vault Manager Engine.

Provides secure Note CRUD operations with strict path traversal validation,
YAML frontmatter management, full-text FTS5 search indexing, wikilinks/backlinks,
and archetype note templates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Union

from bot.vault.archetypes import (
    ConversationLogger,
    DailyNoteHandler,
    EvergreenNoteHandler,
)
from bot.vault.frontmatter import FrontmatterEngine, NoteMetadata
from bot.vault.links import BacklinkGraph, WikiLink
from bot.vault.search import VaultSearchEngine

logger = logging.getLogger(__name__)


class VaultPathSecurityError(Exception):
    """Raised when a note path attempts directory traversal or contains illegal characters."""
    pass


# Security alias
PathTraversalError = VaultPathSecurityError


def sanitize_vault_path(vault_root: Path, relative_path: str) -> Path:
    """
    Sanitize and validate a relative note path against the vault root directory.

    Guards against:
    - Path traversal attacks (`../`, `../../`, root escapes)
    - Null byte injection (`\\0`)
    - Empty or whitespace paths
    - Non-markdown paths (enforces `.md` extension)

    Returns:
        Canonical absolute Path confined strictly within vault_root.
    """
    if not relative_path or not relative_path.strip():
        raise VaultPathSecurityError("Note path cannot be empty.")

    if "\0" in relative_path:
        raise VaultPathSecurityError("Null bytes are prohibited in note paths.")

    clean_str = relative_path.strip().replace("\\", "/").lstrip("/")

    if not clean_str:
        raise VaultPathSecurityError("Note path cannot resolve to an empty string.")

    # Enforce .md extension for note operations
    if not clean_str.endswith(".md"):
        clean_str = f"{clean_str}.md"

    vault_resolved = vault_root.resolve()
    target_path = (vault_resolved / clean_str).resolve()

    try:
        target_path.relative_to(vault_resolved)
    except ValueError:
        raise VaultPathSecurityError(
            f"Directory traversal detected: path '{relative_path}' escapes vault root."
        )

    return target_path


@dataclass
class Note:
    """
    Structured Obsidian Note representation.
    """

    path: str
    content: str
    metadata: NoteMetadata
    raw_body: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "content": self.content,
            "metadata": self.metadata.to_dict(),
            "raw_body": self.raw_body,
        }


class VaultManagerProtocol(Protocol):
    """Protocol definition for VaultManager."""

    def read_note(self, relative_path: str) -> Note: ...
    def write_note(
        self,
        relative_path: str,
        content: str,
        mode: str = "append",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Note: ...
    def search_notes(
        self,
        query: str,
        tag: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]: ...
    def list_notes(self, folder: str = "") -> List[str]: ...
    def append_daily_log(self, content: str, date_str: Optional[str] = None) -> Note: ...


class VaultManager:
    """
    Comprehensive Manager for Obsidian Markdown Knowledge Base.
    """

    def __init__(self, vault_path: Union[str, Path]) -> None:
        self.vault_path = Path(vault_path).resolve()
        self.vault_path.mkdir(parents=True, exist_ok=True)
        self._search_engine = VaultSearchEngine(self.vault_path)
        self._link_graph = BacklinkGraph(self.vault_path)

    def read_note(self, relative_path: str) -> Note:
        """
        Read an Obsidian note, parse frontmatter, and return a structured Note object.
        Raises FileNotFoundError if note does not exist.
        """
        target = sanitize_vault_path(self.vault_path, relative_path)
        if not target.is_file():
            raise FileNotFoundError(f"Note '{relative_path}' not found in vault.")

        content = target.read_text(encoding="utf-8")
        meta, body = FrontmatterEngine.parse(content)
        rel_str = str(target.relative_to(self.vault_path)).replace("\\", "/")
        return Note(path=rel_str, content=content, metadata=meta, raw_body=body)

    def write_note(
        self,
        relative_path: str,
        content: str,
        mode: str = "append",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Note:
        """
        Write or update an Obsidian note.

        Supported modes:
        - 'overwrite': Completely replaces existing body content with new content.
        - 'append': Adds new content to the bottom of the body.
        - 'prepend': Adds new content to the top of the body (below frontmatter).
        """
        target = sanitize_vault_path(self.vault_path, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        existing_meta = NoteMetadata()
        existing_body = ""

        if target.is_file():
            existing_content = target.read_text(encoding="utf-8")
            existing_meta, existing_body = FrontmatterEngine.parse(existing_content)

        # Merge metadata updates if provided
        if metadata:
            for k, v in metadata.items():
                if k == "title":
                    existing_meta.title = str(v) if v is not None else None
                elif k == "tags":
                    existing_meta.tags = v if isinstance(v, list) else [str(v)]
                elif k == "aliases":
                    existing_meta.aliases = v if isinstance(v, list) else [str(v)]
                elif k == "created":
                    existing_meta.created = str(v) if v is not None else None
                elif k == "updated":
                    existing_meta.updated = str(v) if v is not None else None
                else:
                    existing_meta.custom[k] = v

        # Determine final body content based on mode
        if mode == "overwrite" or not target.is_file():
            final_body = content
        elif mode == "prepend":
            final_body = f"{content}\n\n{existing_body}" if existing_body else content
        else:  # append
            final_body = f"{existing_body}\n\n{content}".strip() if existing_body else content

        final_text = FrontmatterEngine.serialize(existing_meta, final_body)
        target.write_text(final_text, encoding="utf-8")

        rel_str = str(target.relative_to(self.vault_path)).replace("\\", "/")

        # Incremental indexing updates
        try:
            stat = target.stat()
            self._search_engine.index_note(rel_str, final_text, stat.st_mtime)
            self._link_graph.update_note_links(rel_str, final_text)
        except Exception as e:
            logger.warning(f"Error updating search index for {rel_str}: {e}")

        return Note(
            path=rel_str,
            content=final_text,
            metadata=existing_meta,
            raw_body=final_body,
        )

    def delete_note(self, relative_path: str) -> bool:
        """
        Delete a note and remove it from search index and link graph.
        Returns True if deleted, False if note did not exist.
        """
        target = sanitize_vault_path(self.vault_path, relative_path)
        if not target.is_file():
            return False

        rel_str = str(target.relative_to(self.vault_path)).replace("\\", "/")
        target.unlink()

        self._search_engine.remove_note(rel_str)
        self._link_graph.remove_note(rel_str)
        return True

    def note_exists(self, relative_path: str) -> bool:
        """Check if note exists safely within vault."""
        try:
            target = sanitize_vault_path(self.vault_path, relative_path)
            return target.is_file()
        except VaultPathSecurityError:
            return False

    def list_notes(self, folder: str = "") -> List[str]:
        """
        List all markdown note paths relative to the vault root.
        Optionally filter to notes within a specific subfolder.
        """
        base = (self.vault_path / folder).resolve() if folder else self.vault_path
        if not base.is_dir():
            return []

        results: List[str] = []
        for f in sorted(base.rglob("*.md")):
            if f.is_file() and not f.name.startswith(".") and ".obsidian" not in str(f) and ".git" not in str(f):
                results.append(str(f.relative_to(self.vault_path)).replace("\\", "/"))

        return results

    def append_daily_log(
        self,
        content: str,
        date_str: Optional[str] = None,
        section: str = "Log",
    ) -> Note:
        """
        Append a log entry into the daily note for date_str (defaults to today).
        """
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        rel_path = DailyNoteHandler.get_daily_path(date_str=date_str)
        target = sanitize_vault_path(self.vault_path, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        existing_content = target.read_text(encoding="utf-8") if target.is_file() else None
        updated_content = DailyNoteHandler.append_entry_to_content(
            existing_content=existing_content,
            entry=content,
            date_str=date_str,
            section_heading=section,
        )

        target.write_text(updated_content, encoding="utf-8")

        # Update index
        rel_str = str(target.relative_to(self.vault_path)).replace("\\", "/")
        try:
            self._search_engine.index_note(rel_str, updated_content, target.stat().st_mtime)
            self._link_graph.update_note_links(rel_str, updated_content)
        except Exception as e:
            logger.debug(f"Index update failed on daily log append: {e}")

        return self.read_note(rel_path)

    def search_notes(
        self,
        query: str = "",
        tag: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search vault notes by keyword and/or tag filter with BM25 ranking and snippets.
        """
        return self._search_engine.search(query=query, tag=tag, limit=limit)

    def get_backlinks(self, note_identifier: str) -> List[str]:
        """
        Get all relative note paths that contain wikilinks pointing to this note.
        """
        return self._link_graph.get_backlinks(note_identifier)

    def get_forward_links(self, relative_path: str) -> List[WikiLink]:
        """
        Get all outgoing wikilinks from a note.
        """
        return self._link_graph.get_forward_links(relative_path)

    def save_conversation(
        self,
        topic: str,
        messages: List[Dict[str, str]],
        summary: str = "",
    ) -> Note:
        """
        Record a conversation dialogue into a structured conversation note in `20-conversations/`.
        """
        rel_path, content = ConversationLogger.create_conversation_note(
            topic=topic,
            messages=messages,
            summary=summary,
        )
        return self.write_note(relative_path=rel_path, content=content, mode="overwrite")

    def create_evergreen_note(
        self,
        title: str,
        content: str,
        summary: str = "",
        tags: Optional[List[str]] = None,
        related_links: Optional[List[str]] = None,
        folder: str = "30-topics",
    ) -> Note:
        """
        Create a new evergreen concept note in the specified topics folder.
        """
        rel_path, note_content = EvergreenNoteHandler.create_evergreen_note(
            title=title,
            content=content,
            summary=summary,
            tags=tags,
            related_links=related_links,
            folder=folder,
        )
        return self.write_note(relative_path=rel_path, content=note_content, mode="overwrite")

    def reindex_all(self, force: bool = False) -> int:
        """Re-scan and re-index the entire vault."""
        count = self._search_engine.index_vault(force=force)
        self._link_graph.build_graph()
        return count
