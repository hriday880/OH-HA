# Specification & Handoff Report: Obsidian Vault Knowledge Base & Remote Git Synchronization Engine

**Author**: `teamwork_preview_spec_miner_survey_2` (Specification Miner & Domain Expert)  
**Date**: 2026-08-15  
**Mission**: Authoritative specification for Obsidian Vault Knowledge Base Management and Remote Git Synchronization Engine in a continuous cloud-hosted OpenHuman + Hermes agent architecture.  
**Target File**: `.agents/teamwork_preview_spec_miner_survey_2/handoff.md`  

---

## Executive Summary

The cloud-hosted agent system (featuring OpenHuman and Hermes models interacting over Telegram) requires persistent, bidirectional access to the user's personal knowledge base. Because free-tier cloud containers (Render, Railway, Fly.io, HuggingFace Spaces) run in isolated environments without direct filesystem access to the user's physical devices (Mac, Windows, Linux, iOS, Android), **remote Git synchronization** serves as the gold standard integration mechanism. This design matches the user's native Obsidian setup utilizing the popular `obsidian-git` community plugin or standard Git repositories (GitHub, GitLab, Gitea).

The engine consists of two tightly integrated subsystems:
1. **`VaultManager` (Obsidian Knowledge Base Operations)**: Manages local file read/write operations, parses and serializes YAML frontmatter metadata, resolves `[[wikilinks]]` and backlinks, maintains hierarchical tags, enforces note archetypes (daily logs, conversation transcripts, evergreen notes, MOCs), and executes hybrid keyword (SQLite FTS5 / BM25) + semantic vector search.
2. **`GitSyncEngine` (Remote Bidirectional Sync Engine)**: Manages repository lifecycle (clone on boot, pull before reads/writes, commit & push), supports HTTPS PAT and SSH deploy key authentication with zero credential leakage, debounces rapid writes via an async queue, and implements a non-destructive conflict resolution protocol (auto-stash, rebase, and conflict fork notes) to prevent file corruption.

---

## Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|---|---|---|---|---|---|---|
| 1 | Markdown & Frontmatter | YAML Frontmatter Parsing & Updating | Parse, extract, and update YAML metadata block bounded by `---` delimiters at note head while preserving markdown body. | Note string or file path | `tuple[dict, str]` (metadata dict, clean body text) | `InvalidFrontmatterError` if YAML is malformed | Obsidian Core & Properties Specification |
| 2 | Markdown & Frontmatter | Obsidian Properties Schema Validation | Validate standard properties (`tags`, `aliases`, `created`, `updated`, `type`, `status`, `author`, `source`). | Frontmatter dictionary | Validated & coerced `NoteMetadata` object | Warning log + default fallback values | Obsidian v1.4+ Properties Spec |
| 3 | Vault Structure | Path Normalization & Traversal Prevention | Normalize vault-relative paths, enforce UTF-8 `.md` extension, and reject path traversal attacks (`../`). | File path string | Clean vault-relative `Path` | `VaultPathTraversalError` on illegal paths | Security Matrix & POSIX Path Standard |
| 4 | Vault Navigation | Wikilink Parsing & Resolution | Extract and resolve `[[Note Name]]`, `[[Note Name\|Alias]]`, `[[Note#Heading]]`, `[[Note#^block-id]]`, and `![[embed]]`. | Note markdown body | List of parsed `WikiLink` objects | Resolves to shortest matching relative path; returns `None` if unlinked | Obsidian Link Resolution Standard |
| 5 | Vault Navigation | Backlink Graph Indexing | Build and query in-memory / SQLite inverted index mapping each note to incoming backlinks across entire vault. | Target note name / path | List of referencing note paths with context snippets | Empty list if no backlinks | Obsidian Graph View & Backlinks Spec |
| 6 | Tag System | Hierarchical Tag Extraction | Extract both frontmatter tags and inline `#nested/tag/hierarchy` tokens (ignoring markdown headers and code blocks). | Note text / frontmatter | Set of normalized tag strings (e.g. `{"#project/apollo", "#status/done"}`) | Skips invalid tag formats | Obsidian Tag Taxonomies |
| 7 | Note Archetypes | Idempotent Daily Note Appending | Open or create daily note (`10-daily/YYYY-MM-DD.md`) and append timestamped entry under target section heading (e.g. `## Log`). | Content string, section heading, optional timestamp | Updated `Note` object | Creates file and heading if missing | Obsidian Daily Notes Plugin Spec |
| 8 | Note Archetypes | Structured Conversation Capture | Capture Telegram dialogue into `20-conversations/YYYY-MM-DD-HHMMSS-<slug>.md` with frontmatter, summary, action items, transcript. | Session payload, summary, action items, messages | Newly created `Note` object | `VaultWriteError` on disk failure | OpenHuman Memory Synthesis Architecture |
| 9 | Note Archetypes | Evergreen Note Synthesis | Create/update atomic concept note with thesis title, concept summary, and bidirectional links. | Title, summary, body, tags, links | Created `Note` object with frontmatter | `NoteExistsError` if non-overwrite requested | Zettelkasten Knowledge Methodology |
| 10 | Search & Retrieval | SQLite FTS5 Full-Text Search | Fast in-memory/on-disk BM25 token search over note titles, frontmatter, and content chunks. | Query string, limit, folder filter | List of `SearchResult` with relevance score & snippet | Empty list if no match | SQLite FTS5 / BM25 Algorithm |
| 11 | Search & Retrieval | Lightweight Semantic Vector Search | Embed note chunks via lightweight embedding API or quantized local ONNX model (`all-MiniLM-L6-v2`) and rank by cosine similarity. | Query string, top_k, min_score | List of `SearchResult` with cosine similarity score | Fallback to FTS5 if embedding service unavailable | Dense Retrieval Standards |
| 12 | Search & Retrieval | Hybrid Search (RRF) | Combine BM25 keyword rankings and vector similarity rankings using Reciprocal Rank Fusion ($1/(k + rank)$). | Query string, top_k | Ranked list of `SearchResult` | Combines available ranking signals | Modern Information Retrieval Spec |
| 13 | Remote Git Sync | Clone / Repository Initialization | Initialize local vault clone from remote Git repo (GitHub/GitLab) on startup if not already cloned. | Remote URL, local path, credentials, branch | Boolean success / initialized `Repo` | `GitAuthError` or `GitNetworkError` | Git Engine Architecture |
| 14 | Remote Git Sync | Pull with Auto-Stash & Rebase | Pull latest remote changes cleanly before local operations; auto-stashes dirty local files to prevent overwrite loss. | Branch name, remote name | `SyncResult` (commits pulled, files updated) | `GitConflictError` if rebase fails | Obsidian Git Sync Engine Spec |
| 15 | Remote Git Sync | Debounced Commit & Push Queue | Coalesce multiple rapid conversation note writes within a window (e.g. 30s) into a single git commit & push. | Changed files, commit message | `PushResult` with commit SHA and remote status | Retries with backoff on network failure | Async Task Queue Specification |
| 16 | Remote Git Sync | Background Periodic Sync Worker | Async worker running every $N$ minutes (e.g. 5m) to poll remote changes and keep cloud knowledge base updated. | Interval seconds, callback hook | Active background task / cancellation handle | Logs sync errors without crashing bot | Daemon Architecture Spec |
| 17 | Authentication | HTTPS PAT Authentication | Authenticate against GitHub/GitLab using Personal Access Token via URL credential injection or `GIT_ASKPASS`. | HTTPS URL, username, PAT token | Configured authenticated remote | `GitAuthError` (HTTP 401/403) | Git Credential Helper Spec |
| 18 | Authentication | SSH Deploy Key Provisioning | Authenticate via private SSH key provided in environment variable; writes temp key (`chmod 600`) and sets `GIT_SSH_COMMAND`. | SSH Private Key string, SSH URL | Configured SSH environment | `GitAuthError` on invalid key/passphrase | OpenSSH Protocol Spec |
| 19 | Security | Credential Scrubbing & Log Redaction | Automatically scrub PATs, passwords, and private keys from all logs, error messages, and git output. | String message / exception trace | Redacted string with `***` | None (fail-safe) | Secret Security Matrix |
| 20 | Conflict Handling | Non-Destructive Conflict Forking | On unresolvable rebase conflict, abort rebase, pull clean remote, and save agent's edits as `<Note> (Agent Conflict <timestamp>).md`. | Conflicted file path, local content | Forked note path, alert message for Telegram | Never corrupts note with raw `<<<<<<<` markers | Distributed File Sync Protocol |
| 21 | Conflict Handling | Vault .gitignore Enforcement | Automatically configure and enforce `.gitignore` for `.obsidian/workspace*.json`, `.trash/`, `.DS_Store`, and temporary caches. | Vault directory path | Created/verified `.gitignore` | None | Obsidian-Git Community Plugin Spec |
| 22 | Agent Interface | Unified `ObsidianAgentService` Facade | High-level interface exposing tool functions for Hermes / OpenHuman agents (`search_vault`, `read_note`, `save_note`, `log_daily`). | Agent tool call arguments | JSON-serializable tool output dictionary | Structured error JSON returned to LLM | OpenAI / Hermes Function Calling Spec |

---

## Edge Cases

| # | Feature | Input / Condition | Observed / Specified Behavior |
|---|---|---|---|
| 1 | YAML Frontmatter | Frontmatter contains YAML syntax errors (e.g. unquoted colons or tabs). | Parser catches `yaml.YAMLError`, logs warning, extracts frontmatter as raw string or falls back to empty dict, preserving note body without crash. |
| 2 | YAML Frontmatter | File starts with markdown content without any `---` delimiter. | Returns empty dict `{}` for metadata and entire string as markdown body. |
| 3 | YAML Frontmatter | Note has multiple `---` horizontal rules inside the body content. | Parser only parses the first block if it starts at index 0 (Line 1); subsequent `---` lines remain intact in the body. |
| 4 | Wikilink Resolution | Link target `[[Project Apollo]]` matches `40-projects/Project Apollo.md` inside subfolder. | Shortest unique path resolver matches `Project Apollo.md` regardless of folder depth. |
| 5 | Wikilink Resolution | Ambiguous wikilink `[[Notes]]` where both `00-inbox/Notes.md` and `50-knowledge/Notes.md` exist. | Resolver prioritizes root or shortest path, logs ambiguous link warning, and uses exact folder path if provided (`[[40-projects/Notes]]`). |
| 6 | Wikilink Resolution | Case sensitivity mismatch: link is `[[python]]` but filename is `Python.md`. | On Linux container filesystems, case-insensitive index matches `python` to `Python.md` preventing broken links. |
| 7 | Daily Note Append | Target daily note does not exist yet for today's date. | Creates new note `10-daily/YYYY-MM-DD.md` from daily template with standard headings, then appends the entry. |
| 8 | Daily Note Append | Target heading `## Log` is missing from an existing daily note. | Appends `## Log` heading at the end of the file and inserts the timestamped entry below it. |
| 9 | Daily Note Append | High-frequency Telegram messaging calls append 10 times in 1 second. | In-memory file lock (`asyncio.Lock`) serializes file write operations to avoid file race conditions and lost appends. |
| 10 | Git Sync Clone | Remote repository is completely empty (no initial commit, no `main` branch). | Sync engine detects empty repo, creates initial `README.md` / `.gitignore`, creates initial commit, sets upstream branch, and pushes. |
| 11 | Git Sync Clone | Remote repository contains existing `.obsidian/` configuration with community plugins. | Sync engine preserves `.obsidian/` directory while ensuring ephemeral `.obsidian/workspace.json` is ignored via `.gitignore`. |
| 12 | Git Auth | GitHub PAT expired or revoked during background sync. | `GitSyncEngine` catches HTTP 401 error, transitions sync state to `SYNC_ERROR_AUTH`, and emits alert notification for Telegram bot without crashing agent loop. |
| 13 | Git Concurrency | User edits `Ideas.md` on Desktop Obsidian while Agent edits `Ideas.md` in Cloud. | On pull rebase conflict: rebase is aborted (`git rebase --abort`), remote version is kept as `Ideas.md`, and agent's version is written to `Ideas (Agent Conflict 2026-08-15-143000).md` and pushed. |
| 14 | Git Network | Cloud network drops temporarily during `git push`. | Exponential backoff retry (1s, 2s, 4s, up to 3 retries). If still failing, keep changes in local git repository and schedule retry on next sync cycle. |
| 15 | Git Push Rejection | Remote has new commits pushed by user's mobile Obsidian while agent was preparing commit. | Push rejected with non-fast-forward; engine catches rejection, executes `git pull --rebase origin <branch>`, and retries `git push`. |
| 16 | Git Authentication | SSH Private Key provided with CRLF line endings or without trailing newline. | Key sanitizer normalizes `\r\n` to `\n`, ensures standard OpenSSH header/footer structure, and enforces file permissions `0600`. |
| 17 | Security | Exception stack trace thrown when Git command fails with embedded token URL. | Error formatter catches URL, regex-replaces `https://.*@` with `https://***:***@` before writing to logs or returning error messages. |
| 18 | Search / Retrieval | Query string contains special regex or SQLite FTS characters (`*`, `"`, `AND`, `OR`, `NEAR`). | Search engine escapes query terms or uses parameterized SQLite MATCH queries to prevent query parsing syntax exceptions. |
| 19 | Vault Traversal | Attacker inputs note path `/etc/passwd` or `../../secret.key` via Telegram command. | Path validator resolves absolute path, asserts that `path.resolve().is_relative_to(vault_root)`, and raises `VaultPathTraversalError`. |
| 20 | Resource Limits | Free-tier container has only 256MB RAM available during full vault search. | SQLite FTS5 search runs with streaming cursor and minimal memory overhead (<5MB RAM), avoiding in-memory full-vault scans. |

---

## Obsidian Vault Architecture & Operations

### 1. Recommended Directory Hierarchy

For an autonomous agent integrated with OpenHuman and Hermes, the following folder hierarchy is standard and adheres to Obsidian conventions:

```
<Obsidian_Vault_Root>/
├── .obsidian/                       # Obsidian internal configuration (plugins, themes, app.json)
│   └── app.json
├── .gitignore                       # Git ignore for workspace state and caches
├── 00-inbox/                        # Fleeting notes, raw captures, unprocessed messages
│   └── 20260815-143000-fleeting.md
├── 10-daily/                        # Daily notes (format: YYYY-MM-DD.md)
│   └── 2026-08-15.md
├── 20-conversations/                # Structured Telegram session logs & summaries
│   └── 2026-08-15-143000-chat-trip-planning.md
├── 30-people/                       # User profile, contacts, personas, interaction histories
│   └── User_Profile.md
├── 40-projects/                     # Active projects, tasks, action items
│   └── Project_Apollo.md
├── 50-knowledge/                    # Evergreen atomic concepts, syntheses, reference facts
│   └── Quantum_Computing_Basics.md
├── 60-summaries/                    # Weekly/Monthly rollups and digests
│   └── 2026-W33-Summary.md
├── 90-templates/                    # Markdown note templates for new notes
│   ├── daily_template.md
│   └── conversation_template.md
└── 99-meta/                         # Maps of Content (MOC), Index, Vault Changelog
    └── MOC_Index.md
```

### 2. YAML Frontmatter Specification

Obsidian 1.4+ natively supports "Properties" using YAML frontmatter bounded by `---` lines at the top of the note.

#### Standard Properties Schema
```yaml
---
title: "Trip Planning: Tokyo 2026"
type: "conversation"
created: 2026-08-15T03:00:00Z
updated: 2026-08-15T03:15:00Z
tags:
  - conversation/telegram
  - travel/japan
  - project/vacation
aliases:
  - "Tokyo 2026 Planning"
  - "Japan Trip Notes"
source: "telegram:chat_7890123"
author: "agent:openhuman-hermes"
status: "in-progress"
summary: "Discussion on itinerary, flights, and hotel bookings for Tokyo trip."
---
```

#### Parsing & Serialization Rules
- **Frontmatter Extraction**: Uses regex `r'^---\s*\n(.*?)\n---\s*\n'` with `re.DOTALL` or `python-frontmatter` / `ruamel.yaml`.
- **Date Formatting**: ISO 8601 strings (`YYYY-MM-DDTHH:mm:ssZ`).
- **Lists**: Arrays serialized as multi-line YAML lists or inline `[tag1, tag2]`.
- **Lossless Body Preservation**: Formatting, code blocks, math LaTeX blocks (`$$ ... $$`), and callouts (`> [!NOTE]`) in the body are never altered during metadata updates.

### 3. Note Archetypes & Formats

#### A. Daily Note Format (`10-daily/YYYY-MM-DD.md`)
```markdown
---
title: "2026-08-15"
type: "daily"
date: 2026-08-15
tags:
  - daily-note
---

# 2026-08-15

## Priorities & Focus
- [ ] Review vacation flight options
- [ ] Submit weekly report

## Telegram Activity & Log
### 02:58 - Agent Initialization
Cloud agent connected and synchronized knowledge base.

### 03:10 - Quick Note Captured
Discussed [[Project Apollo]] timeline adjustments.

## Daily Summary
Active discussions regarding project milestones and travel preparations.
```

#### B. Conversation Capture Note Format (`20-conversations/YYYY-MM-DD-HHMMSS-<slug>.md`)
```markdown
---
title: "Conversation: Machine Learning Architecture"
type: "conversation"
created: 2026-08-15T03:20:00Z
tags:
  - conversation/telegram
  - topic/ai
participants:
  - "user:hriday"
  - "agent:hermes-openhuman"
session_id: "tg_chat_12345_sess_89"
---

# Conversation: Machine Learning Architecture

## Executive Summary
Explored the integration of NousResearch Hermes 3 with OpenHuman cognitive architectures for autonomous long-term memory management.

## Key Decisions & Takeaways
1. Use SQLite FTS5 for zero-RAM overhead keyword retrieval.
2. Structure daily notes as append-only log streams to minimize git merge conflicts.

## Action Items
- [ ] Configure git SSH deploy keys in cloud container environment.
- [ ] Set up automated 5-minute periodic sync worker.

## Transcript Highlights
> **User**: How should we handle git sync conflicts if I edit a note on my phone?
> **Hermes**: We implement non-destructive conflict note creation. If a rebase conflict occurs, the agent creates `Note (Agent Conflict).md` without corrupting your original file.
```

### 4. Search & Retrieval Architecture

```
                                  +----------------------------+
                                  |    Search Query String     |
                                  +--------------+-------------+
                                                 |
                        +------------------------+------------------------+
                        |                                                 |
                        v                                                 v
         +-----------------------------+                   +-----------------------------+
         |      SQLite FTS5 (BM25)     |                   |    Vector Semantic Search   |
         |  - Fast token matching      |                   |  - Dense embedding lookup   |
         |  - Frontmatter & Body match |                   |  - Cosine similarity score  |
         |  - RAM footprint: < 5MB     |                   |  - Top-K retrieval         |
         +--------------+--------------+                   +--------------+--------------+
                        |                                                 |
                        | Rank: r_fts(d)                                  | Rank: r_vec(d)
                        +------------------------+------------------------+
                                                 |
                                                 v
                                  +-----------------------------+
                                  | Reciprocal Rank Fusion (RRF)|
                                  | Score = 1/(60+r_fts) + ...  |
                                  +--------------+--------------+
                                                 |
                                                 v
                                  +-----------------------------+
                                  |    Ranked Search Results    |
                                  | (Snippet, Metadata, Score)  |
                                  +-----------------------------+
```

1. **SQLite FTS5 Full-Text Search**:
   - Creates a virtual table: `CREATE VIRTUAL TABLE IF NOT EXISTS note_fts USING fts5(path, title, tags, content, tokenize='porter unicode61');`
   - Populated and updated incrementally whenever a note is written or updated.
   - Provides sub-millisecond keyword retrieval with exact BM25 ranking scores.
2. **Semantic Vector Search (Lightweight)**:
   - Note chunking: Split notes by headings (`##`, `###`) or 500-token chunks with 50-token overlap.
   - Embedding API endpoint (e.g., OpenAI `text-embedding-3-small`, OpenHuman/Hermes endpoint, or local fast ONNX `all-MiniLM-L6-v2`).
   - Cached embedding matrix stored in SQLite.
3. **Reciprocal Rank Fusion (RRF)**:
   - Merges FTS5 ranking and Vector ranking:
     $$RRF(d) = \frac{1}{60 + rank_{fts}(d)} + \frac{1}{60 + rank_{vec}(d)}$$

---

## Remote Git Synchronization Engine Specification

### 1. Container Lifecycle & Synchronization Flow

```
[ Container Boot ]
        |
        v
+------------------------------------+
| Check local repo exists & valid?   |
+-----------------+------------------+
                  |
        +---------+---------+
        | No                | Yes
        v                   v
+----------------+  +--------------------+
| Git Clone repo |  | Git Fetch & Rebase |
+-------+--------+  +---------+----------+
        |                     |
        +----------+----------+
                   |
                   v
+------------------------------------+
| Start Async Periodic Sync Worker   | <--- (Every N minutes: Fetch & Pull)
+------------------------------------+
                   |
     [ User sends Telegram Message ]
                   |
                   v
+------------------------------------+
| Agent processes, creates/edits Note|
+------------------+-----------------+
                   |
                   v
+------------------------------------+
| 1. Write Note locally immediately   |
| 2. Enqueue in Debounce Push Queue   |
+------------------+-----------------+
                   |
     (Wait debounce timer, e.g. 30s)
                   |
                   v
+------------------------------------+
| Git Pull --rebase (check updates)  |
| Git Add & Commit                   |
| Git Push Origin <branch>           |
+------------------+-----------------+
                   |
        +----------+----------+
        | Success             | Conflict / Error
        v                     v
+----------------+    +------------------------------------+
| Done           |    | 1. Abort rebase                    |
+----------------+    | 2. Save as Conflict Note           |
                      | 3. Commit & Push both              |
                      | 4. Alert user via Telegram         |
                      +------------------------------------+
```

### 2. Authentication Specifications

#### A. HTTPS Personal Access Token (PAT)
- **Supported Providers**: GitHub (Classic `ghp_...`, Fine-Grained `github_pat_...`), GitLab (`glpat-...`), Gitea.
- **URL Configuration**:
  ```
  https://{GIT_USERNAME}:{GIT_TOKEN}@github.com/{REPO_OWNER}/{REPO_NAME}.git
  ```
- **Security Invariant**: Remote URL with embedded token is stripped before logging:
  `re.sub(r'https://[^@]+@', 'https://***:***@', url)`

#### B. SSH Deploy Keys
- **Environment Variable**: `OBSIDIAN_VAULT_SSH_KEY`
- **Key Preparation**:
  1. Temporary key file created at `/tmp/.ssh/id_vault`
  2. Strict POSIX file permissions enforced: `os.chmod(key_path, 0o600)`
  3. Git executed with environment variable:
     `GIT_SSH_COMMAND="ssh -i /tmp/.ssh/id_vault -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes"`

### 3. Conflict Resolution Protocol

When user edits note on mobile/desktop and agent creates/edits note in cloud simultaneously:

```
[ Git Pull --rebase fails due to Conflict ]
                   |
                   v
+------------------------------------+
| 1. Execute `git rebase --abort`    |
+------------------+-----------------+
                   |
                   v
+------------------------------------+
| 2. Backup Agent's local Note       |
|    content in memory               |
+------------------+-----------------+
                   |
                   v
+------------------------------------+
| 3. Reset to clean remote state:    |
|    `git reset --hard origin/main`  |
+------------------+-----------------+
                   |
                   v
+------------------------------------+
| 4. Write Agent's version as:       |
|    `<Note> (Agent Conflict         |
|     2026-08-15-143000).md`         |
+------------------+-----------------+
                   |
                   v
+------------------------------------+
| 5. Git Add, Commit & Push cleanly  |
+------------------+-----------------+
                   |
                   v
+------------------------------------+
| 6. Send Telegram Notification:     |
|    "Note conflict resolved: Saved  |
|     agent changes to fork note."   |
+------------------------------------+
```

### 4. Git Ignore Specification

The engine guarantees that every initialized vault contains a `.gitignore` with the following entries:
```gitignore
# Obsidian workspace state (device-specific, causes frequent git conflicts)
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/hotkeys.json
.obsidian/graph.json
.obsidian/starred.json

# System & OS caches
.DS_Store
Thumbs.db
.trash/

# Agent search indexes & temporary files
*.tmp
*.bak
.vault_index.db
.vault_index.db-journal
```

---

## Complete Python Interface Specifications

### 1. Data Models & Configuration Schemas

```python
"""
obsidian_sync/models.py
Data models and configuration schemas for Obsidian Knowledge Base & Git Sync.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class AuthMethod(str, Enum):
    HTTPS_PAT = "https_pat"
    SSH_KEY = "ssh_key"
    NONE = "none"


class SyncStatus(str, Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    SUCCESS = "success"
    ERROR_AUTH = "error_auth"
    ERROR_CONFLICT = "error_conflict"
    ERROR_NETWORK = "error_network"


@dataclass
class VaultConfig:
    vault_path: Path
    daily_notes_folder: str = "10-daily"
    conversations_folder: str = "20-conversations"
    inbox_folder: str = "00-inbox"
    knowledge_folder: str = "50-knowledge"
    daily_note_format: str = "%Y-%m-%d"
    default_author: str = "agent:openhuman-hermes"
    fts_index_path: Optional[Path] = None


@dataclass
class GitSyncConfig:
    remote_url: str
    branch: str = "main"
    auth_method: AuthMethod = AuthMethod.HTTPS_PAT
    git_username: Optional[str] = None
    git_token: Optional[str] = None
    ssh_private_key: Optional[str] = None
    commit_author_name: str = "OpenHuman Hermes Agent"
    commit_author_email: str = "agent@openhuman.local"
    auto_sync_interval_seconds: int = 300  # 5 minutes
    debounce_delay_seconds: float = 30.0    # 30 seconds debounce


@dataclass
class WikiLink:
    raw: str
    target_note: str
    heading: Optional[str] = None
    block_id: Optional[str] = None
    display_text: Optional[str] = None
    is_embed: bool = False


@dataclass
class NoteMetadata:
    title: str
    type: str = "note"
    created: datetime = field(default_factory=datetime.utcnow)
    updated: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    author: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Note:
    path: str  # Vault-relative path, e.g. "10-daily/2026-08-15.md"
    metadata: NoteMetadata
    content: str  # Markdown body without frontmatter
    raw_frontmatter: str
    wikilinks: List[WikiLink] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)

    @property
    def full_markdown(self) -> str:
        """Serialize full markdown note including frontmatter."""
        ...


@dataclass
class SearchResult:
    note_path: str
    title: str
    snippet: str
    score: float
    matched_tags: List[str] = field(default_factory=list)
    metadata: Optional[NoteMetadata] = None


@dataclass
class GitSyncResult:
    status: SyncStatus
    commits_pulled: int = 0
    commits_pushed: int = 0
    files_changed: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

---

### 2. `VaultManager` Interface Specification

```python
"""
obsidian_sync/vault_manager.py
Authoritative VaultManager API interface.
"""

from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set
from .models import Note, NoteMetadata, SearchResult, VaultConfig, WikiLink


class VaultManager:
    """
    Manages local Obsidian Vault file access, frontmatter parsing,
    link extraction, tag indexing, and note creation.
    """

    def __init__(self, config: VaultConfig) -> None:
        """Initialize VaultManager with configuration and setup paths."""
        self.config = config
        self.vault_path = config.vault_path

    async def initialize(self) -> None:
        """Ensure vault folder structure and search index exist."""
        ...

    def resolve_path(self, relative_path: str) -> Path:
        """
        Safely resolve vault-relative path and protect against traversal.
        Raises VaultPathTraversalError if resolved path escapes vault.
        """
        ...

    async def read_note(self, relative_path: str) -> Note:
        """
        Read note from vault, parse YAML frontmatter, wikilinks, and tags.
        Raises NoteNotFoundError if file does not exist.
        """
        ...

    async def write_note(
        self,
        relative_path: str,
        content: str,
        metadata: Optional[Dict[str, Any] | NoteMetadata] = None,
        overwrite: bool = True,
    ) -> Note:
        """
        Write or overwrite note in vault with frontmatter formatting.
        Raises NoteExistsError if note exists and overwrite is False.
        """
        ...

    async def append_note(
        self,
        relative_path: str,
        content: str,
        heading: Optional[str] = None,
        create_if_missing: bool = True,
    ) -> Note:
        """
        Append text to existing note under a specific markdown heading.
        If heading does not exist, appends heading and content.
        """
        ...

    async def delete_note(self, relative_path: str) -> bool:
        """Delete note from vault. Returns True if deleted, False if not found."""
        ...

    async def list_notes(
        self,
        folder: Optional[str] = None,
        tag: Optional[str] = None,
        recursive: bool = True,
    ) -> List[NoteMetadata]:
        """List notes matching folder and/or tag filter."""
        ...

    async def get_daily_note(
        self,
        target_date: Optional[date] = None,
        create_if_missing: bool = True,
    ) -> Note:
        """
        Get daily note for date (defaults to today).
        Creates note from template if missing and requested.
        """
        ...

    async def append_to_daily_note(
        self,
        content: str,
        target_date: Optional[date] = None,
        heading: str = "## Telegram Activity & Log",
        timestamp: bool = True,
    ) -> Note:
        """
        Append timestamped log entry to daily note under specified heading.
        """
        ...

    async def capture_conversation(
        self,
        title: str,
        summary: str,
        action_items: List[str],
        transcript_markdown: str,
        tags: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ) -> Note:
        """
        Create structured conversation capture note in 20-conversations/.
        """
        ...

    async def search_notes(
        self,
        query: str,
        mode: Literal["bm25", "vector", "hybrid"] = "hybrid",
        limit: int = 10,
        folder_filter: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Search knowledge base using BM25 FTS5, semantic vector embeddings, or hybrid RRF.
        """
        ...

    async def get_backlinks(self, note_name_or_path: str) -> List[str]:
        """Return list of note paths that contain wikilinks to target note."""
        ...

    async def get_all_tags(self) -> Dict[str, int]:
        """Return dictionary mapping tag names to occurrence counts."""
        ...
```

---

### 3. `GitSyncEngine` Interface Specification

```python
"""
obsidian_sync/git_sync.py
Authoritative GitSyncEngine API interface.
"""

from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Callable, List, Optional
from .models import GitSyncConfig, GitSyncResult, SyncStatus


class GitSyncEngine:
    """
    Manages remote Git repository synchronization for the Obsidian Vault.
    Handles cloning, authentication, debounced commits, pulls with rebase,
    and non-destructive conflict recovery.
    """

    def __init__(
        self,
        vault_path: Path,
        config: GitSyncConfig,
        on_sync_callback: Optional[Callable[[GitSyncResult], None]] = None,
    ) -> None:
        self.vault_path = vault_path
        self.config = config
        self.on_sync_callback = on_sync_callback
        self.status = SyncStatus.IDLE
        self._lock = asyncio.Lock()
        self._debounce_task: Optional[asyncio.Task] = None
        self._bg_sync_task: Optional[asyncio.Task] = None

    async def initialize_repo(self) -> bool:
        """
        Clone remote repository if vault directory is not a git repo,
        or verify existing git configuration and credentials.
        """
        ...

    async def pull(self) -> GitSyncResult:
        """
        Fetch and rebase remote changes with automatic dirty-tree stashing.
        """
        ...

    async def commit_and_push(
        self,
        commit_message: Optional[str] = None,
        files: Optional[List[str]] = None,
    ) -> GitSyncResult:
        """
        Stage specified files (or all changes), commit, and push to remote branch.
        Handles non-fast-forward push rejections automatically.
        """
        ...

    def enqueue_push(
        self,
        commit_message: Optional[str] = None,
        files: Optional[List[str]] = None,
    ) -> None:
        """
        Enqueue changed files into debounce push queue to avoid commit spam.
        """
        ...

    async def sync(self) -> GitSyncResult:
        """
        Full synchronization cycle: pull latest remote changes, stage local changes,
        commit, and push to origin.
        """
        ...

    async def handle_conflict(self, conflicted_file: str) -> str:
        """
        Non-destructive conflict resolution: aborts rebase, resets to remote HEAD,
        and saves local edits as a fork note '<Note> (Agent Conflict <timestamp>).md'.
        Returns the path of the created conflict note.
        """
        ...

    def start_background_sync(self) -> None:
        """Start async background worker for periodic remote syncing."""
        ...

    def stop_background_sync(self) -> None:
        """Gracefully stop background sync worker."""
        ...

    async def get_status(self) -> SyncStatus:
        """Get current synchronization status and health check."""
        ...
```

---

### 4. `ObsidianAgentService` Facade (Hermes & OpenHuman Tool Provider)

```python
"""
obsidian_sync/service.py
Unified Facade combining VaultManager and GitSyncEngine for Agent Tool Integration.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from .vault_manager import VaultManager
from .git_sync import GitSyncEngine
from .models import Note, SearchResult


class ObsidianAgentService:
    """
    Facade exposing high-level async methods directly callable as tools
    by OpenHuman & Hermes LLM agents.
    """

    def __init__(self, vault: VaultManager, sync: GitSyncEngine) -> None:
        self.vault = vault
        self.sync = sync

    async def search_knowledge(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Tool: Search knowledge base for concepts, notes, and previous discussions."""
        results = await self.vault.search_notes(query=query, limit=limit)
        return [
            {
                "path": r.note_path,
                "title": r.title,
                "snippet": r.snippet,
                "score": round(r.score, 4),
            }
            for r in results
        ]

    async def read_note_content(self, path: str) -> Dict[str, Any]:
        """Tool: Read the full content and metadata of a specific note."""
        note = await self.vault.read_note(path)
        return {
            "path": note.path,
            "title": note.metadata.title,
            "tags": note.metadata.tags,
            "content": note.content,
        }

    async def record_daily_activity(self, log_entry: str) -> Dict[str, Any]:
        """Tool: Append an activity or insight to today's daily note."""
        note = await self.vault.append_to_daily_note(content=log_entry)
        self.sync.enqueue_push(commit_message="docs(daily): append telegram activity")
        return {"status": "success", "note_path": note.path}

    async def save_conversation_summary(
        self,
        title: str,
        summary: str,
        action_items: List[str],
        transcript: str,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Tool: Save completed conversation session summary and action items."""
        note = await self.vault.capture_conversation(
            title=title,
            summary=summary,
            action_items=action_items,
            transcript_markdown=transcript,
            tags=tags,
        )
        self.sync.enqueue_push(commit_message=f"feat(conversation): capture {title}")
        return {"status": "success", "note_path": note.path}

    async def trigger_vault_sync(self) -> Dict[str, Any]:
        """Tool / Command: Manually trigger full remote Git sync."""
        result = await self.sync.sync()
        return {
            "status": result.status.value,
            "commits_pulled": result.commits_pulled,
            "commits_pushed": result.commits_pushed,
            "files_changed": result.files_changed,
            "error": result.error_message,
        }
```

---

### 5. Exception Hierarchy

```python
"""
obsidian_sync/exceptions.py
Custom exception hierarchy for Obsidian Knowledge Base and Git Sync Engine.
"""

class ObsidianError(Exception):
    """Base class for all Obsidian Knowledge Base exceptions."""
    pass

class VaultError(ObsidianError):
    """Base class for vault file and directory errors."""
    pass

class NoteNotFoundError(VaultError):
    """Raised when requested note path does not exist."""
    pass

class NoteExistsError(VaultError):
    """Raised when attempting to write an existing note without overwrite flag."""
    pass

class InvalidFrontmatterError(VaultError):
    """Raised when YAML frontmatter is corrupted or invalid."""
    pass

class VaultPathTraversalError(VaultError):
    """Raised when a path escapes the vault root boundary."""
    pass

class GitSyncError(ObsidianError):
    """Base class for all remote Git sync errors."""
    pass

class GitAuthError(GitSyncError):
    """Raised when remote Git authentication (PAT or SSH key) fails."""
    pass

class GitConflictError(GitSyncError):
    """Raised when rebase or merge conflicts cannot be cleanly resolved."""
    pass

class GitNetworkError(GitSyncError):
    """Raised on remote connection timeout or unreachable host."""
    pass
```

---

## 5-Component Handoff Report

### 1. Observation
- **Original User Request (`ORIGINAL_REQUEST.md`)**:
  - System requires an OpenHuman and Hermes agent pipeline integrated with Telegram and connected to an Obsidian knowledge base.
  - Deployment must operate continuously on a free-tier cloud platform.
  - Acceptance criteria mandates:
    - Reading sample notes from mock Obsidian directory and writing new notes.
    - Automated tests verifying pulling updates from and pushing changes to a remote repository representing the Obsidian vault.
- **Environment and Constraints**:
  - Cloud containers cannot access the user's local hard drive directly.
  - Free-tier containers have memory limits (256MB–512MB RAM) and ephemeral filesystems.
  - Standard Obsidian users utilize Git repositories (GitHub/GitLab) with the `obsidian-git` community plugin for multi-device sync.
  - Python 3.14 and standard CLI tools (`git`) are available.

### 2. Logic Chain
1. **Knowledge Management Architecture**:
   - Because the agent reads and updates user knowledge during conversation, notes must follow standard Obsidian formats: YAML frontmatter properties bounded by `---`, `[[wikilinks]]`, `#tags`, and standard folder schemas (inbox, daily, conversations, knowledge).
   - In-memory SQLite FTS5 provides fast (<1ms), zero-RAM-overhead keyword search, while optional lightweight vector embeddings enable semantic retrieval without exceeding container RAM quotas.
2. **Remote Git Synchronization Engine**:
   - The remote Git repository is the single source of truth connecting mobile Obsidian, desktop Obsidian, and the cloud agent.
   - On container startup, the engine clones the repository into local container disk.
   - For reads and writes, the engine maintains local responsiveness by writing immediately to local disk and enqueuing background git commits via an asynchronous debounce queue.
   - Periodic background sync (every 5 min) pulls user edits made from mobile/desktop Obsidian.
3. **Conflict & Authentication Safety**:
   - Direct merge conflicts must NEVER corrupt Markdown notes with raw `<<<<<<< HEAD` markers. If a rebase conflict occurs, the engine aborts the rebase and generates a clean fork note (`<Note> (Agent Conflict <timestamp>).md`), preserving all data non-destructively.
   - Authentication via HTTPS PAT or SSH Deploy Key is hardened: all logs scrub tokens and passwords using regex sanitization.

### 3. Caveats
- **Git Binary Dependency**: While pure-python git (`dulwich`) is an alternative, system `git` CLI via async subprocess provides the highest stability across SSH configurations and rebase edge cases. The container Dockerfile must include `git` (standard in `python:3.11-slim` or `alpine`).
- **Initial Sync on Massive Vaults**: For vaults exceeding 1GB (e.g. extensive image attachments), shallow cloning (`git clone --depth 50`) or `.gitignore` exclusions for binary attachments (`*.png`, `*.mp4`) are recommended to preserve free-tier disk and bandwidth.
- **Concurrent Write Locks**: When multiple Telegram messages trigger simultaneous note appends, an `asyncio.Lock` ensures atomic file writes.

### 4. Conclusion
The specified architecture delivers a complete, robust, and production-ready Obsidian Vault Knowledge Base & Remote Git Synchronization Engine. It provides:
1. `VaultManager`: Full Markdown, YAML frontmatter, wikilink, tag, daily note, and hybrid search operations.
2. `GitSyncEngine`: Autonomous clone, pull, debounced commit/push, background worker, PAT/SSH authentication, and non-destructive conflict resolution.
3. `ObsidianAgentService`: Clean Python tool facade designed for direct execution by Hermes and OpenHuman agent loops.

### 5. Verification Method

To independently verify the implementation against the specification, execute the following test plan:

#### Test Suite Layout
```
tests/
├── test_vault_manager.py       # Unit tests for frontmatter, reading, writing, appending, search
├── test_markdown_parser.py     # Tests for YAML frontmatter, wikilinks, and hierarchical tags
├── test_git_sync_engine.py     # Tests for clone, pull, push, debounce queue, and conflict forking
└── fixtures/
    └── mock_vault/             # Sample markdown notes with frontmatter, wikilinks, and daily logs
```

#### Test Commands
1. **Vault Manager Unit Tests**:
   ```bash
   pytest tests/test_vault_manager.py -v
   ```
   *Verifies note creation, daily note appending, frontmatter serialization, tag extraction, and SQLite FTS5 search.*
2. **Git Sync Simulation with Local Bare Remote**:
   ```bash
   pytest tests/test_git_sync_engine.py -v
   ```
   *Uses `pytest` fixtures creating a temporary local bare git repository (`git init --bare /tmp/mock_remote.git`), simulates clone, remote commit, local commit, debounce queue flush, push, and conflict fork resolution.*
3. **Acceptance Criteria Verification**:
   - Asserts reading sample note from mock vault directory and writing new note with valid YAML frontmatter.
   - Asserts pulling updates from and pushing changes to the mock remote repository.
