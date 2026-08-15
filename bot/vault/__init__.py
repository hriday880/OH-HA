"""
Obsidian Vault Knowledge Base Engine.

Provides frontmatter parsing, note CRUD, path traversal guards, wikilinks/backlinks,
SQLite FTS5 full-text search, and note archetypes (daily notes, conversations, concepts).
"""

from bot.vault.frontmatter import (
    FrontmatterEngine,
    FrontmatterParser,
    NoteMetadata,
    parse_frontmatter,
    serialize_frontmatter,
)
from bot.vault.links import (
    Backlink,
    BacklinkGraph,
    LinkGraph,
    WikiLink,
    Wikilink,
    extract_wikilinks,
)
from bot.vault.search import (
    SearchResult,
    VaultSearchEngine,
    VaultSearchIndex,
)
from bot.vault.archetypes import (
    ConversationLogger,
    DailyNoteHandler,
    EvergreenNoteHandler,
    render_template,
)
from bot.vault.manager import (
    Note,
    PathTraversalError,
    VaultManager,
    VaultManagerProtocol,
    VaultPathSecurityError,
    sanitize_vault_path,
)

__all__ = [
    "FrontmatterEngine",
    "FrontmatterParser",
    "NoteMetadata",
    "parse_frontmatter",
    "serialize_frontmatter",
    "Backlink",
    "BacklinkGraph",
    "LinkGraph",
    "WikiLink",
    "Wikilink",
    "extract_wikilinks",
    "SearchResult",
    "VaultSearchEngine",
    "VaultSearchIndex",
    "ConversationLogger",
    "DailyNoteHandler",
    "EvergreenNoteHandler",
    "render_template",
    "Note",
    "PathTraversalError",
    "VaultManager",
    "VaultManagerProtocol",
    "VaultPathSecurityError",
    "sanitize_vault_path",
]
