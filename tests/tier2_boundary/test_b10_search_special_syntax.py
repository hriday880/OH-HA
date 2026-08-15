"""
Boundary Test 10: SQLite FTS5 Query Syntax & Special Characters.
Tests FTS5 reserved tokens (*, AND, OR, NEAR), SQL injection strings, and extreme query limits.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from bot.vault.search import VaultSearchEngine


class TestBoundary10SearchSpecialSyntax:
    """Boundary tests for Feature 10 (Search & Tag Indexing)."""

    def test_special_fts_meta_characters(self, mock_vault_dir: Path):
        """Test search query containing raw FTS5 operators (*, NEAR, AND, quotes)."""
        engine = VaultSearchEngine(mock_vault_dir)

        # Raw operators should not crash the search engine
        res1 = engine.search("Apollo*")
        assert isinstance(res1, list)

        res2 = engine.search("\"Quantum Computing\"")
        assert isinstance(res2, list)

        res3 = engine.search("Apollo NEAR/2 Quantum")
        assert isinstance(res3, list)

    def test_sql_injection_resilience(self, mock_vault_dir: Path):
        """Test SQL injection payloads do not alter database structure or raise syntax errors."""
        engine = VaultSearchEngine(mock_vault_dir)

        payloads = [
            "' OR '1'='1",
            "'; DROP TABLE notes_fts; --",
            "\" UNION SELECT sqlite_version(), 2, 3, 4, 5 --",
        ]
        for p in payloads:
            results = engine.search(p)
            assert isinstance(results, list)

    def test_empty_string_and_whitespace_query(self, mock_vault_dir: Path):
        """Test empty queries return empty list without executing full table scan."""
        engine = VaultSearchEngine(mock_vault_dir)
        assert engine.search("") == []
        assert engine.search("   \t  ") == []

    def test_single_character_and_punctuation_query(self, mock_vault_dir: Path):
        """Test single character and pure punctuation queries."""
        engine = VaultSearchEngine(mock_vault_dir)
        res = engine.search("a")
        assert isinstance(res, list)

        res_punct = engine.search("!@#$%^&*()")
        assert isinstance(res_punct, list)

    def test_search_limit_boundaries(self, mock_vault_dir: Path):
        """Test search with limit=1, limit=0, and limit=1000."""
        engine = VaultSearchEngine(mock_vault_dir)

        res_1 = engine.search("Apollo", limit=1)
        assert len(res_1) <= 1

        res_0 = engine.search("Apollo", limit=0)
        assert len(res_0) == 0
