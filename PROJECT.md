# Project: OpenHuman & Hermes Telegram Agent with Obsidian Knowledge Base & Cloud Deployment

## Architecture Overview
The system is an autonomous, continuously running personal AI companion that interfaces with users via Telegram, manages knowledge via an Obsidian Markdown Vault with bidirectional remote Git synchronization, and operates reliably within free-tier cloud container constraints (256MB–512MB RAM, ephemeral disks).

```
 +-------------------------------------------------------------------------+
 |                          Cloud Container Runtime                        |
 |                                                                         |
 |  +-----------------------+                +--------------------------+  |
 |  |    HTTP Health Server  |                |   Telegram Bot Service   |  |
 |  |    (aiohttp GET /health|                |   (Long-Polling / Async) |  |
 |  +-----------+-----------+                +------------+-------------+  |
 |              |                                         |                |
 |              +--------------------+--------------------+                |
 |                                   |                                     |
 |                                   v                                     |
 |                   +-------------------------------+                     |
 |                   |   OpenHuman & Hermes Pipeline |                     |
 |                   |   (Split-Brain & Tool Routing)|                     |
 |                   +---------------+---------------+                     |
 |                                   | (Tool Calls)                        |
 |                                   v                                     |
 |                   +-------------------------------+                     |
 |                   |    Obsidian Vault Manager     |                     |
 |                   |    (Markdown, Frontmatter,    |                     |
 |                   |     Search, Wikilinks)        |                     |
 |                   +---------------+---------------+                     |
 |                                   |                                     |
 |                                   v (Auto-sync queue)                   |
 |                   +-------------------------------+                     |
 |                   |    Git Synchronization Engine |                     |
 |                   |    (Clone, Pull/Rebase, Push, |                     |
 |                   |     Conflict Resolution)      |                     |
 |                   +---------------+---------------+                     |
 |                                   |                                     |
 +-----------------------------------|-------------------------------------+
                                     | (HTTPS / SSH)
                                     v
                       +---------------------------+
                       | Remote Git Repository     |
                       | (GitHub / GitLab / Gitea) |
                       | User's Obsidian Vault     |
                       +---------------------------+
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Configuration & Environment Validation | Typed settings loading (`pydantic_settings` / `dataclass`), fail-fast env validation, secret masking | M1 | Survey 1,3 |
| 2 | LLM Provider Adapter Interface | Abstract async interface for OpenAI, OpenRouter, Groq, Together, Ollama, HuggingFace | M1 | Survey 1 |
| 3 | Hermes Tool Calling & Prompt Engine | ChatML XML (`<tools>`, `<tool_call>`, `<tool_response>`) and OpenAI tool calling JSON schemas | M1 | Survey 1 |
| 4 | OpenHuman Persona & Memory Mapping | Persona management and memory tree routing mapped to Obsidian vault folders | M1 | Survey 1,2 |
| 5 | Split-Brain Reflex & Intent Router | Fast command/intent triage paired with deep multi-step Hermes reasoning loop | M1 | Survey 1 |
| 6 | Obsidian Markdown & Frontmatter Engine | Parse, validate, and serialize YAML frontmatter metadata and markdown bodies | M2 | Survey 2 |
| 7 | Path Normalization & Traversal Security | Enforce `.md` extensions, sanitize paths, reject traversal attacks (`../../`) | M2 | Survey 1,2 |
| 8 | Obsidian Note CRUD & Archetypes | Read, write, append, prepend notes (Daily notes, Conversation logs, Concepts, MOCs) | M2 | Survey 2 |
| 9 | Wikilink & Backlink Engine | Parse and resolve `[[wikilinks]]`, aliases, and build vault backlink graph | M2 | Survey 2 |
| 10 | Hybrid Search & Tag Indexing | Hierarchical tag extraction, SQLite FTS5 full-text BM25 search, and semantic ranking | M2 | Survey 2 |
| 11 | Git Repository Lifecycle & Auth | Git repository clone on startup, HTTPS PAT & SSH deploy key authentication without credential leak | M3 | Survey 2,3 |
| 12 | Bidirectional Pull/Rebase & Auto-Stash | Pull remote changes before reads/writes, auto-stash dirty state, handle fast-forward/rebase | M3 | Survey 2,3 |
| 13 | Debounced Commit & Push Engine | Coalesce rapid note updates into batched git commits and push with retry & backoff | M3 | Survey 2,3 |
| 14 | Non-Destructive Conflict Resolution | On rebase conflict, preserve remote note and fork agent edits to conflict note | M3 | Survey 2,3 |
| 15 | Telegram Async Bot Lifecycle | `python-telegram-bot` v20+ async runner with long-polling (`drop_pending_updates=True`) | M4 | Survey 1,3 |
| 16 | Telegram Command & Message Handlers | Slash commands (`/start`, `/help`, `/note`, `/sync`, `/status`, `/ask`) & natural conversation pipeline | M4 | Survey 1 |
| 17 | UX Resilience & Whitelist Security | Message chunking (<=4096 chars), HTML formatting sanitization, typing indicator heartbeat, user ID whitelist | M4 | Survey 1 |
| 18 | Unified HTTP Health & Keepalive Server | Async `/health` and `/metrics` server on `$PORT` to satisfy free-tier keepalive monitors | M4 | Survey 3 |
| 19 | Continuous Daemon & Graceful Shutdown | Process lifecycle manager handling `SIGTERM`/`SIGINT`, in-flight task draining, and final Git sync flush | M4 | Survey 3 |
| 20 | Multi-Stage Minimal Docker Container | Hardened Dockerfile (<130MB), non-root user (`botuser`), `tini` PID 1, low-memory tuning (`MALLOC_ARENA_MAX=2`) | M5 | Survey 3 |
| 21 | Free-Tier Cloud Deployment Blueprints | Configuration files (`render.yaml`, `fly.toml`, `docker-compose.yml`, `entrypoint.sh`, `.env.example`) | M5 | Survey 3 |
| 22 | Comprehensive E2E Verification & Adversarial Hardening | Pass 100% of E2E test suite (Tiers 1-4) covering all 4 user acceptance criteria and Tier 5 adversarial tests | M6 | Survey 3, User Request |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Core Config, LLM Adapters & Hermes/OpenHuman Agent | Features 1, 2, 3, 4, 5. Config management, async LLM providers (Hermes/OpenHuman), prompt engine, tool call schemas, reflex router. | none | PLANNED |
| 2 | Obsidian Vault Knowledge Base Engine | Features 6, 7, 8, 9, 10. Frontmatter parser, note CRUD, path traversal guards, wikilinks/backlinks, SQLite FTS5 search, daily/conversation note archetypes. | M1 | PLANNED |
| 3 | Remote Git Synchronization Engine | Features 11, 12, 13, 14. Git repo clone/pull/push, HTTPS PAT/SSH key auth, debounced commit queue, non-destructive conflict handling. | M2 | PLANNED |
| 4 | Telegram Bot, HTTP Health Server & Continuous Daemon | Features 15, 16, 17, 18, 19. Async Telegram bot, commands, message chunker, typing heartbeat, security whitelist, `/health` server, graceful shutdown. | M1, M2, M3 | PLANNED |
| 5 | Free-Tier Containerization & Cloud Deployment Configs | Features 20, 21. Multi-stage Dockerfile, `entrypoint.sh`, non-root user, `render.yaml`, `fly.toml`, `docker-compose.yml`, deployment docs. | M4 | PLANNED |
| 6 | Final E2E Test Suite Validation & Adversarial Hardening | Feature 22. Full E2E verification across Tiers 1-4 (AC 1-4) and Tier 5 adversarial coverage hardening. | M1, M2, M3, M4, M5, E2E Test Track | PLANNED |

## Interface Contracts

### 1. `LLMProvider` ↔ `AgentPipeline`
```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]

@dataclass
class LLMResponse:
    content: Optional[str]
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw_response: Optional[Dict[str, Any]] = None

class BaseLLMProvider(ABC):
    @abstractmethod
    async def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        pass
```

### 2. `VaultManager` ↔ `AgentPipeline` & `GitSyncEngine`
```python
@dataclass
class NoteMetadata:
    title: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    created: Optional[str] = None
    updated: Optional[str] = None
    custom: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Note:
    path: str
    content: str
    metadata: NoteMetadata
    raw_body: str

class VaultManagerProtocol(Protocol):
    def read_note(self, relative_path: str) -> Note: ...
    def write_note(self, relative_path: str, content: str, mode: str = "append", metadata: Optional[Dict[str, Any]] = None) -> Note: ...
    def search_notes(self, query: str, tag: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]: ...
    def list_notes(self, folder: str = "") -> List[str]: ...
    def append_daily_log(self, content: str, date_str: Optional[str] = None) -> Note: ...
```

### 3. `GitSyncEngine` ↔ `VaultManager` & `Daemon`
```python
@dataclass
class SyncStatus:
    is_synced: bool
    last_sync_time: Optional[datetime]
    uncommitted_changes: int
    unpushed_commits: int
    error: Optional[str]

class GitSyncProtocol(Protocol):
    async def initialize_repo(self) -> bool: ...
    async def pull_and_rebase(self) -> bool: ...
    async def commit_and_push(self, commit_message: Optional[str] = None) -> bool: ...
    async def sync_now(self) -> SyncStatus: ...
    def get_status(self) -> SyncStatus: ...
```

### 4. `TelegramBot` ↔ `AgentPipeline`
```python
class TelegramBotProtocol(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def process_user_message(self, user_id: int, text: str) -> str: ...
```

## Code Layout
```
/Users/hriday/Documents/OH and HA/
├── bot/
│   ├── __init__.py
│   ├── config.py                 # Pydantic/dataclass configuration & env validation
│   ├── main.py                   # Main daemon entrypoint (co-schedules bot, health server, sync)
│   ├── health.py                 # Async HTTP health & keepalive server (GET /health, GET /metrics)
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── pipeline.py           # OpenHuman & Hermes agent pipeline, tool router
│   │   ├── persona.py            # OpenHuman persona, memory tree context builder
│   │   ├── providers.py          # LLMProvider implementations (OpenRouter, Groq, Mock, etc.)
│   │   ├── prompts.py            # Hermes ChatML XML & system prompts
│   │   └── tools.py              # Tool registry and execution dispatch
│   ├── vault/
│   │   ├── __init__.py
│   │   ├── manager.py            # Obsidian VaultManager (read/write/search/metadata)
│   │   ├── frontmatter.py        # YAML frontmatter parser and serializer
│   │   ├── search.py             # SQLite FTS5 full-text & tag search
│   │   ├── links.py              # Wikilinks and backlink resolver
│   │   └── archetypes.py         # Daily notes, conversation capture, evergreen notes
│   ├── git_sync/
│   │   ├── __init__.py
│   │   ├── engine.py             # GitSyncEngine (clone, pull, commit, push)
│   │   ├── auth.py               # HTTPS PAT and SSH deploy key management
│   │   └── conflict.py           # Non-destructive conflict resolution handler
│   └── telegram/
│       ├── __init__.py
│       ├── bot.py                # Telegram bot lifecycle & handlers
│       ├── commands.py           # Command routers (/start, /help, /note, /sync, /status, /ask)
│       ├── formatters.py         # Message chunking, Markdown/HTML entity sanitizers
│       └── security.py           # User whitelist verification middleware
├── deploy/
│   ├── Dockerfile                # Multi-stage hardened production Dockerfile
│   ├── entrypoint.sh             # Container startup script (Git auth, vault init, exec)
│   ├── docker-compose.yml        # Local/server compose deployment
│   ├── render.yaml               # Render free-tier blueprint
│   ├── fly.toml                  # Fly.io microVM configuration
│   └── .env.example              # Documented environment variable template
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Shared fixtures (mock Telegram, mock LLM, temp vault, bare git repo)
│   ├── tier1_feature/            # Tier 1 tests: isolated feature coverage (>=5 per feature)
│   ├── tier2_boundary/           # Tier 2 tests: boundaries, edge cases, error conditions (>=5 per feature)
│   ├── tier3_pairwise/           # Tier 3 tests: cross-feature combination tests
│   ├── tier4_application/        # Tier 4 tests: end-to-end user workflows & acceptance criteria (AC 1-4)
│   └── tier5_adversarial/       # Tier 5 tests: white-box stress testing and security audits
├── requirements.txt              # Production Python dependencies
├── requirements-dev.txt          # Testing & development dependencies
├── README.md                     # Complete user guide and deployment instructions
├── PROJECT.md                    # Project blueprint and milestone tracking
├── TEST_INFRA.md                 # E2E testing framework specification
└── ORIGINAL_REQUEST.md           # Authoritative user requirements
```
