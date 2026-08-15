"""
Obsidian SQLite FTS5 Full-Text Search, Tag Indexing & BM25 Ranking Engine.

Provides fast BM25 ranked keyword queries, hierarchical tag filtering (#project/apollo),
query sanitization preventing FTS5 syntax crashes / SQL injections, snippet extraction,
and incremental index updates based on file timestamps.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from bot.vault.frontmatter import FrontmatterEngine, NoteMetadata

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """
    Search match result with relevance score and contextual snippet.
    """

    path: str
    title: str
    tags: List[str]
    snippet: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "title": self.title,
            "tags": self.tags,
            "snippet": self.snippet,
            "rank": self.score,
            "score": self.score,
            "metadata": self.metadata,
        }


def _sanitize_fts5_query(raw_query: str) -> str:
    """
    Sanitize raw search query to prevent SQLite FTS5 OperationalError exceptions.
    Safely preserves prefix searches (*) and phrase quotes while escaping problematic syntax.
    """
    cleaned = raw_query.strip()
    if not cleaned:
        return ""

    # Check if query is already a valid balanced quoted phrase e.g. "Quantum Computing"
    if cleaned.startswith('"') and cleaned.endswith('"') and cleaned.count('"') == 2:
        inner = cleaned[1:-1].replace('"', '""').strip()
        if inner:
            return f'"{inner}"'

    # Check for NEAR operator e.g. "Apollo NEAR/2 Quantum"
    near_match = re.match(r'^([\w\-]+)\s+(NEAR(?:/\d+)?)\s+([\w\-]+)$', cleaned, re.IGNORECASE)
    if near_match:
        term1, op, term2 = near_match.groups()
        return f"{term1} {op.upper()} {term2}"

    # Extract tokens (words, wildcards, operators)
    tokens: List[str] = []
    # Pattern matches quoted phrases or single words (allowing trailing *)
    token_pattern = re.compile(r'"([^"]*)"|([\w\-]+(?:\*)?)|([^\s\w\-]+)')

    for match in token_pattern.finditer(cleaned):
        phrase, word, punct = match.groups()
        if phrase is not None and phrase.strip():
            safe_phrase = phrase.replace('"', '""').strip()
            tokens.append(f'"{safe_phrase}"')
        elif word is not None and word.strip():
            upper_word = word.upper()
            if upper_word in {"AND", "OR", "NOT"}:
                tokens.append(upper_word)
            else:
                tokens.append(word)
        elif punct is not None and punct.strip():
            # If punctuation contains wildcard *, attach to previous token or treat safely
            if punct == "*" and tokens:
                tokens[-1] = f"{tokens[-1].rstrip('*')}*"

    # Filter out standalone operators at edges or back-to-back operators
    clean_tokens: List[str] = []
    for i, tok in enumerate(tokens):
        if tok in {"AND", "OR", "NOT"}:
            if clean_tokens and clean_tokens[-1] not in {"AND", "OR", "NOT"}:
                clean_tokens.append(tok)
        else:
            clean_tokens.append(tok)

    while clean_tokens and clean_tokens[-1] in {"AND", "OR", "NOT"}:
        clean_tokens.pop()
    while clean_tokens and clean_tokens[0] in {"AND", "OR", "NOT"}:
        clean_tokens.pop(0)

    if not clean_tokens:
        # Fallback to double quoting any alphanumeric sequence
        words = re.findall(r"[\w]+", cleaned)
        if words:
            return " ".join(f'"{w}"' for w in words)
        return ""

    return " ".join(clean_tokens)


class VaultSearchEngine:
    """
    SQLite FTS5 Full-Text and Tag Search Indexer for Obsidian Vault.
    """

    def __init__(
        self,
        vault_path: Path,
        db_path: Optional[Path] = None,
    ) -> None:
        self.vault_path = Path(vault_path).resolve()
        if db_path:
            self.db_path = Path(db_path).resolve()
        else:
            obsidian_dir = self.vault_path / ".obsidian"
            obsidian_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = obsidian_dir / "search_index.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.index_vault()

    def _get_connection(self) -> sqlite3.Connection:
        """Create sqlite3 connection with standard settings."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize SQLite FTS5 table and metadata tables."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # FTS5 Virtual Table
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                    path,
                    title,
                    tags,
                    content,
                    tokenize = 'porter unicode61'
                )
            """)

            # Metadata Table for Incremental Indexing
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notes_meta (
                    path TEXT PRIMARY KEY,
                    title TEXT,
                    tags_str TEXT,
                    mtime REAL,
                    content_hash TEXT,
                    frontmatter_json TEXT
                )
            """)

            # Tag Index Table for Hierarchical Filtering
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS note_tags (
                    path TEXT,
                    tag TEXT,
                    normalized_tag TEXT,
                    PRIMARY KEY (path, tag)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tag_norm ON note_tags(normalized_tag)")
            conn.commit()
        finally:
            conn.close()

    def index_vault(self, force: bool = False) -> int:
        """
        Scan vault directory and update full-text and tag index incrementally.
        Returns count of notes indexed.
        """
        if not self.vault_path.is_dir():
            return 0

        conn = self._get_connection()
        indexed_count = 0
        try:
            cursor = conn.cursor()
            existing_paths: Set[str] = set()

            for md_file in self.vault_path.rglob("*.md"):
                if md_file.name.startswith(".") or ".obsidian" in str(md_file) or ".git" in str(md_file):
                    continue

                try:
                    stat = md_file.stat()
                    mtime = stat.st_mtime
                    text = md_file.read_text(encoding="utf-8")
                except Exception as e:
                    logger.debug(f"Error reading {md_file} for indexing: {e}")
                    continue

                rel_path = str(md_file.relative_to(self.vault_path)).replace("\\", "/")
                existing_paths.add(rel_path)

                content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

                if not force:
                    # Check if note has changed
                    cursor.execute(
                        "SELECT mtime, content_hash FROM notes_meta WHERE path = ?",
                        (rel_path,),
                    )
                    row = cursor.fetchone()
                    if row and row["content_hash"] == content_hash and abs(row["mtime"] - mtime) < 0.001:
                        continue

                self._index_single_note_tx(cursor, rel_path, text, mtime, content_hash)
                indexed_count += 1

            # Delete notes from index that no longer exist on disk
            cursor.execute("SELECT path FROM notes_meta")
            for row in cursor.fetchall():
                path = row["path"]
                if path not in existing_paths:
                    cursor.execute("DELETE FROM notes_fts WHERE path = ?", (path,))
                    cursor.execute("DELETE FROM notes_meta WHERE path = ?", (path,))
                    cursor.execute("DELETE FROM note_tags WHERE path = ?", (path,))

            conn.commit()
        finally:
            conn.close()

        return indexed_count

    def _index_single_note_tx(
        self,
        cursor: sqlite3.Cursor,
        rel_path: str,
        content: str,
        mtime: float,
        content_hash: str,
    ) -> None:
        """Helper to index a single note within an active transaction."""
        meta, body = FrontmatterEngine.parse(content)
        stem = Path(rel_path).stem
        title = meta.title or stem

        # Extract all tags (frontmatter + inline body tags)
        inline_tags = FrontmatterEngine.extract_inline_tags(body)
        all_tags = list(meta.tags)
        for itag in inline_tags:
            if itag not in all_tags:
                all_tags.append(itag)

        tags_str = " ".join(all_tags)
        # Combined searchable text
        full_searchable = f"{title} {tags_str} {body}"

        # 1. Update notes_fts
        cursor.execute("DELETE FROM notes_fts WHERE path = ?", (rel_path,))
        cursor.execute(
            "INSERT INTO notes_fts(path, title, tags, content) VALUES(?, ?, ?, ?)",
            (rel_path, title, tags_str, full_searchable),
        )

        # 2. Update notes_meta
        meta_dict = meta.to_dict()
        cursor.execute(
            """
            INSERT OR REPLACE INTO notes_meta(path, title, tags_str, mtime, content_hash, frontmatter_json)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (rel_path, title, tags_str, mtime, content_hash, json.dumps(meta_dict, default=str)),
        )


        # 3. Update note_tags
        cursor.execute("DELETE FROM note_tags WHERE path = ?", (rel_path,))
        for tag in all_tags:
            norm_tag = tag.strip().lstrip("#").lower()
            cursor.execute(
                "INSERT OR REPLACE INTO note_tags(path, tag, normalized_tag) VALUES(?, ?, ?)",
                (rel_path, tag, norm_tag),
            )

    def index_note(self, rel_path: str, content: str, mtime: Optional[float] = None) -> None:
        """Incrementally index or update a single note."""
        clean_path = rel_path.replace("\\", "/").lstrip("/")
        if not clean_path.endswith(".md"):
            clean_path = f"{clean_path}.md"

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        note_mtime = mtime if mtime is not None else 0.0

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            self._index_single_note_tx(cursor, clean_path, content, note_mtime, content_hash)
            conn.commit()
        finally:
            conn.close()

    def remove_note(self, rel_path: str) -> None:
        """Remove a note from search index."""
        clean_path = rel_path.replace("\\", "/").lstrip("/")
        if not clean_path.endswith(".md"):
            clean_path = f"{clean_path}.md"

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM notes_fts WHERE path = ?", (clean_path,))
            cursor.execute("DELETE FROM notes_meta WHERE path = ?", (clean_path,))
            cursor.execute("DELETE FROM note_tags WHERE path = ?", (clean_path,))
            conn.commit()
        finally:
            conn.close()

    def search(
        self,
        query: str = "",
        tag: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search notes by keyword query, tag, or combination thereof.
        Returns list of result dictionaries sorted by relevance.
        """
        if limit <= 0:
            return []

        clean_query = query.strip() if query else ""
        clean_tag = tag.strip().lstrip("#").lower() if tag else ""

        if not clean_query and not clean_tag:
            return []

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            results: List[Dict[str, Any]] = []

            # 1. Tag-only query
            if not clean_query and clean_tag:
                cursor.execute(
                    """
                    SELECT DISTINCT m.path, m.title, m.tags_str, m.frontmatter_json
                    FROM note_tags t
                    JOIN notes_meta m ON t.path = m.path
                    WHERE t.normalized_tag = ? OR t.normalized_tag LIKE ?
                    LIMIT ?
                    """,
                    (clean_tag, f"{clean_tag}/%", limit),
                )
                for row in cursor.fetchall():
                    meta_dict = json.loads(row["frontmatter_json"]) if row["frontmatter_json"] else {}
                    tags_list = row["tags_str"].split() if row["tags_str"] else []
                    results.append({
                        "path": row["path"],
                        "title": row["title"],
                        "tags": tags_list,
                        "snippet": "",
                        "rank": 0.0,
                        "score": 0.0,
                        "metadata": meta_dict,
                    })
                return results

            # 2. FTS5 Query (with optional tag filtering)
            sanitized_fts = _sanitize_fts5_query(clean_query)
            if not sanitized_fts:
                # If query contains no searchable tokens (e.g. pure punctuation), return empty list
                return []

            try:
                if clean_tag:
                    cursor.execute(
                        """
                        SELECT f.path, f.title, f.tags,
                               snippet(notes_fts, 3, '<b>', '</b>', '...', 15) AS snip,
                               bm25(notes_fts) AS rank_score
                        FROM notes_fts f
                        JOIN note_tags t ON f.path = t.path
                        WHERE notes_fts MATCH ? AND (t.normalized_tag = ? OR t.normalized_tag LIKE ?)
                        GROUP BY f.path
                        ORDER BY rank_score ASC
                        LIMIT ?
                        """,
                        (sanitized_fts, clean_tag, f"{clean_tag}/%", limit),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT path, title, tags,
                               snippet(notes_fts, 3, '<b>', '</b>', '...', 15) AS snip,
                               bm25(notes_fts) AS rank_score
                        FROM notes_fts
                        WHERE notes_fts MATCH ?
                        ORDER BY rank_score ASC
                        LIMIT ?
                        """,
                        (sanitized_fts, limit),
                    )

                for row in cursor.fetchall():
                    tags_list = row["tags"].split() if row["tags"] else []
                    results.append({
                        "path": row["path"],
                        "title": row["title"],
                        "tags": tags_list,
                        "snippet": row["snip"],
                        "rank": float(row["rank_score"]),
                        "score": float(row["rank_score"]),
                    })
            except sqlite3.OperationalError as e:
                logger.debug(f"FTS5 MATCH error with query '{sanitized_fts}': {e}. Retrying with literal tokens.")
                # Fallback: quote each word
                words = re.findall(r"[\w]+", clean_query)
                if not words:
                    return []
                fallback_query = " ".join(f'"{w}"' for w in words)
                try:
                    cursor.execute(
                        """
                        SELECT path, title, tags,
                               snippet(notes_fts, 3, '<b>', '</b>', '...', 15) AS snip,
                               bm25(notes_fts) AS rank_score
                        FROM notes_fts
                        WHERE notes_fts MATCH ?
                        ORDER BY rank_score ASC
                        LIMIT ?
                        """,
                        (fallback_query, limit),
                    )
                    for row in cursor.fetchall():
                        tags_list = row["tags"].split() if row["tags"] else []
                        results.append({
                            "path": row["path"],
                            "title": row["title"],
                            "tags": tags_list,
                            "snippet": row["snip"],
                            "rank": float(row["rank_score"]),
                            "score": float(row["rank_score"]),
                        })
                except Exception:
                    return []

            return results
        finally:
            conn.close()


# Alias for contract compatibility
VaultSearchIndex = VaultSearchEngine
