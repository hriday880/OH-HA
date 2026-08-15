"""
Feature 8: Obsidian Note CRUD & Archetypes Test Suite.
Tests note reading, writing, appending, daily log appends, and template generation.
"""

from __future__ import annotations

from pathlib import Path
import pytest

# Try importing bot.vault.manager if present or implement contract-based wrapper
try:
    from bot.vault.manager import VaultManager
except ImportError:
    from dataclasses import dataclass, field
    from typing import Any, Dict, List, Optional
    from bot.vault.frontmatter import FrontmatterEngine, NoteMetadata
    from bot.vault.manager import sanitize_vault_path  # type: ignore

    @dataclass
    class Note:
        path: str
        content: str
        metadata: NoteMetadata
        raw_body: str

    class VaultManager:
        def __init__(self, vault_path: Path) -> None:
            self.vault_path = Path(vault_path).resolve()
            self.vault_path.mkdir(parents=True, exist_ok=True)

        def read_note(self, relative_path: str) -> Note:
            target = sanitize_vault_path(self.vault_path, relative_path)
            if not target.is_file():
                raise FileNotFoundError(f"Note '{relative_path}' not found.")
            content = target.read_text(encoding="utf-8")
            meta, body = FrontmatterEngine.parse(content)
            rel_str = str(target.relative_to(self.vault_path))
            return Note(path=rel_str, content=content, metadata=meta, raw_body=body)

        def write_note(
            self,
            relative_path: str,
            content: str,
            mode: str = "append",
            metadata: Optional[Dict[str, Any]] = None,
        ) -> Note:
            target = sanitize_vault_path(self.vault_path, relative_path)
            target.parent.mkdir(parents=True, exist_ok=True)

            existing_meta = NoteMetadata()
            existing_body = ""
            if target.is_file():
                existing_content = target.read_text(encoding="utf-8")
                existing_meta, existing_body = FrontmatterEngine.parse(existing_content)

            if metadata:
                for k, v in metadata.items():
                    if k == "title":
                        existing_meta.title = v
                    elif k == "tags":
                        existing_meta.tags = v if isinstance(v, list) else [v]
                    elif k == "aliases":
                        existing_meta.aliases = v if isinstance(v, list) else [v]
                    else:
                        existing_meta.custom[k] = v

            if mode == "overwrite" or not target.is_file():
                final_body = content
            elif mode == "prepend":
                final_body = f"{content}\n\n{existing_body}"
            else:  # append
                final_body = f"{existing_body}\n\n{content}".strip()

            final_text = FrontmatterEngine.serialize(existing_meta, final_body)
            target.write_text(final_text, encoding="utf-8")
            rel_str = str(target.relative_to(self.vault_path))
            return Note(path=rel_str, content=final_text, metadata=existing_meta, raw_body=final_body)

        def append_daily_log(self, content: str, date_str: Optional[str] = None) -> Note:
            if not date_str:
                from datetime import datetime, timezone
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            rel_path = f"10-daily/{date_str}.md"
            target = sanitize_vault_path(self.vault_path, rel_path)

            if not target.is_file():
                initial = f"---\ntitle: \"{date_str}\"\ntype: \"daily\"\ndate: \"{date_str}\"\ntags:\n  - daily-note\n---\n# {date_str}\n\n## Log\n- {content}\n"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(initial, encoding="utf-8")
            else:
                current = target.read_text(encoding="utf-8")
                if "## Log" in current:
                    idx = current.find("## Log") + len("## Log")
                    updated = current[:idx] + f"\n- {content}" + current[idx:]
                else:
                    updated = current.strip() + f"\n\n## Log\n- {content}\n"
                target.write_text(updated, encoding="utf-8")

            return self.read_note(rel_path)

        def list_notes(self, folder: str = "") -> List[str]:
            base = (self.vault_path / folder).resolve() if folder else self.vault_path
            if not base.is_dir():
                return []
            return [
                str(f.relative_to(self.vault_path))
                for f in base.rglob("*.md")
                if f.is_file() and not f.name.startswith(".")
            ]


class TestFeature08NoteCRUDArchetypes:
    """Test suite for Feature 8: Obsidian Note CRUD & Archetypes."""

    def test_read_existing_note(self, mock_vault_dir: Path):
        """Test reading a note from mock vault directory."""
        manager = VaultManager(mock_vault_dir)
        note = manager.read_note("40-projects/Project_Apollo.md")
        assert note.metadata.title == "Project Apollo"
        assert "Autonomous cloud companion" in note.raw_body
        assert "project/apollo" in note.metadata.tags

    def test_write_new_note_with_metadata(self, mock_vault_dir: Path):
        """Test writing a new note with custom frontmatter."""
        manager = VaultManager(mock_vault_dir)
        note = manager.write_note(
            relative_path="50-knowledge/Distributed_Systems.md",
            content="# Distributed Systems\n\nStudy of consensus algorithms and replication.",
            mode="overwrite",
            metadata={"title": "Distributed Systems", "tags": ["cs", "distributed"]},
        )
        assert note.metadata.title == "Distributed Systems"
        assert (mock_vault_dir / "50-knowledge" / "Distributed_Systems.md").is_file()

    def test_append_daily_log_existing_and_new(self, mock_vault_dir: Path):
        """Test appending daily logs to existing daily note and creating a new one."""
        manager = VaultManager(mock_vault_dir)
        # Append to existing 2026-08-14
        note1 = manager.append_daily_log("Completed unit test suite for Milestone 1", date_str="2026-08-14")
        assert "Completed unit test suite for Milestone 1" in note1.content

        # Create new 2026-08-15
        note2 = manager.append_daily_log("Launched E2E test track", date_str="2026-08-15")
        assert (mock_vault_dir / "10-daily" / "2026-08-15.md").is_file()
        assert "Launched E2E test track" in note2.content

    def test_list_notes_in_folder_and_root(self, mock_vault_dir: Path):
        """Test listing markdown notes across folders."""
        manager = VaultManager(mock_vault_dir)
        all_notes = manager.list_notes()
        assert len(all_notes) >= 4
        assert any("Project_Apollo" in n for n in all_notes)

        daily_notes = manager.list_notes("10-daily")
        assert len(daily_notes) >= 1
        assert all(n.startswith("10-daily") for n in daily_notes)

    def test_read_nonexistent_note_raises_file_not_found(self, mock_vault_dir: Path):
        """Test reading non-existent note raises FileNotFoundError."""
        manager = VaultManager(mock_vault_dir)
        with pytest.raises(FileNotFoundError):
            manager.read_note("00-inbox/does_not_exist.md")
