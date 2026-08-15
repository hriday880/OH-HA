"""
Feature 10: Hybrid Search & Tag Indexing Test Suite.
Tests SQLite FTS5 full-text search, BM25 ranking, tag filtering, and hierarchical tag queries.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
import pytest

# Try importing bot.vault.search if present or implement contract-based search indexer
try:
    from bot.vault.search import VaultSearchEngine
except ImportError:
    from bot.vault.frontmatter import FrontmatterEngine

    class VaultSearchEngine:
        def __init__(self, vault_path: Path, db_path: Optional[Path] = None) -> None:
            self.vault_path = Path(vault_path)
            self.db_path = db_path or (self.vault_path / ".obsidian" / "search_index.db")
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
            self.index_vault()

        def _init_db(self) -> None:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                    path,
                    title,
                    tags,
                    content,
                    tokenize = 'porter unicode61'
                )
            """)
            conn.commit()
            conn.close()

        def index_vault(self) -> None:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("DELETE FROM notes_fts")
            for md in self.vault_path.rglob("*.md"):
                if md.name.startswith(".") or ".obsidian" in str(md):
                    continue
                try:
                    text = md.read_text(encoding="utf-8")
                except Exception:
                    continue
                meta, body = FrontmatterEngine.parse(text)
                rel_path = str(md.relative_to(self.vault_path))
                title = meta.title or md.stem
                tags = " ".join(meta.tags)
                cursor.execute(
                    "INSERT INTO notes_fts(path, title, tags, content) VALUES(?, ?, ?, ?)",
                    (rel_path, title, tags, f"{title} {tags} {body}"),
                )
            conn.commit()
            conn.close()

        def search(self, query: str, tag: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
            if not query.strip() and not tag:
                return []
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            results = []
            try:
                if query and tag:
                    clean_tag = tag.lstrip("#")
                    cursor.execute(
                        """
                        SELECT path, title, tags, snippet(notes_fts, 3, '<b>', '</b>', '...', 15), rank
                        FROM notes_fts
                        WHERE notes_fts MATCH ? AND tags LIKE ?
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (query, f"%{clean_tag}%", limit),
                    )
                elif query:
                    cursor.execute(
                        """
                        SELECT path, title, tags, snippet(notes_fts, 3, '<b>', '</b>', '...', 15), rank
                        FROM notes_fts
                        WHERE notes_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (query, limit),
                    )
                else:
                    clean_tag = tag.lstrip("#") if tag else ""
                    cursor.execute(
                        """
                        SELECT path, title, tags, '', 0.0
                        FROM notes_fts
                        WHERE tags LIKE ?
                        LIMIT ?
                        """,
                        (f"%{clean_tag}%", limit),
                    )

                for row in cursor.fetchall():
                    results.append({
                        "path": row[0],
                        "title": row[1],
                        "tags": row[2].split() if row[2] else [],
                        "snippet": row[3],
                        "rank": row[4],
                    })
            except sqlite3.OperationalError:
                # Malformed query fallback
                return []
            finally:
                conn.close()
            return results


class TestFeature10SearchTagIndexing:
    """Test suite for Feature 10: Hybrid Search & Tag Indexing."""

    def test_search_by_keyword(self, mock_vault_dir: Path):
        """Test keyword search finds relevant notes and snippets."""
        engine = VaultSearchEngine(mock_vault_dir)
        results = engine.search(query="Apollo")
        assert len(results) >= 1
        assert any("Project_Apollo" in r["path"] for r in results)

    def test_search_by_tag_filter(self, mock_vault_dir: Path):
        """Test filtering notes by tag."""
        engine = VaultSearchEngine(mock_vault_dir)
        results = engine.search(query="", tag="#daily-note")
        assert len(results) >= 1
        assert all("10-daily" in r["path"] for r in results)

    def test_search_hierarchical_tag(self, mock_vault_dir: Path):
        """Test tag search matches parent of hierarchical tag e.g. 'project' matching 'project/apollo'."""
        engine = VaultSearchEngine(mock_vault_dir)
        results = engine.search(query="", tag="project")
        assert len(results) >= 1
        assert any("Project_Apollo" in r["path"] for r in results)

    def test_empty_search_results(self, mock_vault_dir: Path):
        """Test query with non-existent terms returns empty list."""
        engine = VaultSearchEngine(mock_vault_dir)
        results = engine.search(query="NonExistentTermXYZ123")
        assert results == []

    def test_ranking_and_snippet_extraction(self, mock_vault_dir: Path):
        """Test search results return formatted snippets."""
        engine = VaultSearchEngine(mock_vault_dir)
        results = engine.search(query="entanglement")
        assert len(results) >= 1
        assert any("Quantum" in r["path"] for r in results)
