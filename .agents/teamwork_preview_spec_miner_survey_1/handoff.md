# Specification & Survey Report: OpenHuman & Hermes Agent Pipeline with Telegram Bot Architecture

**Author**: `teamwork_preview_spec_miner_survey_1`  
**Date**: 2026-08-14T21:35:00Z  
**Target Milestone**: Step 0 (Survey Track - Explorer 1)  
**Assigned Scope**: Core Agent Pipeline (Hermes & OpenHuman integration, Multi-model orchestration, Provider Adapters), Telegram Bot Architecture (Async Framework, Long-polling vs Webhooks, Commands, UX & Resilience), and Tool Execution / Action Interface with Obsidian.

---

## 1. Executive Summary & Specification Tables

### Features Discovered
| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Agent Pipeline | Hermes 3 Tool Calling (ChatML XML) | Native structured function calling via `<tools>`, `<tool_call>`, `<tool_response>` tags within ChatML text stream. | System prompt with tool definitions in `<tools>`, user messages. | `<tool_call>{"name": ..., "arguments": {...}}</tool_call>` | Falls back to natural conversation if schema invalid or syntax malformed. | Hermes 3 Spec / NousResearch ArXiv |
| 2 | Agent Pipeline | OpenAI-Compatible Tool Schema Adapter | Standardized JSON schema (`tools: [...]`, `tool_choice: "auto"`) for OpenRouter, Groq, Together, vLLM, Ollama. | List of `ToolDefinition` objects, messages array. | Assistant message with `tool_calls` array or standard content. | `APIError`, HTTP 4xx/5xx caught with exponential backoff & failover. | OpenAI / OpenRouter API Standard |
| 3 | Agent Pipeline | OpenHuman Persona & Memory Tree | Personal AI companion persona integrated with hierarchical memory tree mirroring Obsidian notes for episodic & semantic context. | User message, short-term history, retrieved Obsidian notes/profile. | Persona-aligned system prompt and contextual memory injection. | Empty memory fallback; graceful degradation on missing context. | OpenHuman Agent Framework Spec |
| 4 | Agent Pipeline | Split-Brain Orchestration | Fast reflex triage (intent routing/classifier) coupled with deep Hermes reasoning engine. | Inbound user message string. | Route decision (`command`, `quick_qa`, `deep_reasoning`, `tool_call`). | Defaults to full reasoning agent if classification is ambiguous. | OpenHuman Split-Brain Architecture |
| 5 | Agent Pipeline | Provider Adapter Interface (`LLMProvider`) | Abstract async interface supporting OpenAI, OpenRouter, Groq, Together AI, Ollama, and Hugging Face endpoints. | `ChatCompletionRequest` (messages, tools, temperature, max_tokens). | `ChatCompletionResponse` (content, tool_calls, usage). | Retries on 429/503 with exponential backoff; fallback provider switch. | Provider API Specifications |
| 6 | Agent Pipeline | Scratchpad Reasoning / CoT | Inner monologue `<thought>...</thought>` or `<scratch_pad>` for multi-step planning before generating tool calls. | Prompt with reasoning instruction. | Filtered/logged reasoning tokens followed by user-facing reply. | Stripped from end-user Telegram messages to maintain clean UX. | Hermes 3 Agentic Reasoning Guidelines |
| 7 | Telegram Bot | Async Application Lifecycle | Non-blocking bot runner using `python-telegram-bot` v20+ async engine (`ApplicationBuilder`). | Bot Token, Update stream from Telegram API. | Dispatched handler executions across async event loop. | Global error handler logs tracebacks and notifies user gracefully. | PTB v20+ Documentation |
| 8 | Telegram Bot | Long-Polling with Drop Pending Updates | Free-tier compatible update retrieval (`run_polling(drop_pending_updates=True)`) requiring no public IP or SSL certs. | Polling timeout, allowed updates list. | Continuous async update stream. | Network reconnect loop with automatic jittered backoff on connection loss. | Telegram Bot API Specs |
| 9 | Telegram Bot | Command Handlers (`/start`, `/help`, `/note`, `/sync`, `/status`, `/ask`) | Dedicated slash-command routers providing immediate feedback, shortcuts, and administrative control. | `/command [arguments]` text. | Formatted status, help message, or trigger of background vault sync. | Command syntax error messages with usage hints. | Telegram Bot Command Protocol |
| 10 | Telegram Bot | Natural Conversation Pipeline | General message handler routing unstructured queries to the OpenHuman/Hermes agent loop. | Text messages (`filters.TEXT & ~filters.COMMAND`). | Synthesized natural language responses with vault citations. | Friendly fallback message if LLM provider fails completely. | Telegram Message Routing Specs |
| 11 | Telegram Bot | Message Chunking & Splitting | Smart boundary-aware chunking respecting Telegram's 4,096 character limit per message without breaking Markdown. | Text strings > 4096 characters. | Sequential array of message chunks (split on `\n\n`, `\n`, or words). | Truncation safety fallback if single word exceeds limit. | Telegram API Limit Documentation |
| 12 | Telegram Bot | Safe Markdown Formatting & Sanitization | Sanitizer/parser converting LLM Markdown to valid Telegram MarkdownV2 / HTML entities without parse crashes. | Raw Markdown from LLM. | Escaped MarkdownV2 string or sanitized HTML. | Falls back to plain text delivery if parser fails to prevent message drops. | Telegram Entity Parsing Docs |
| 13 | Telegram Bot | Continuous Typing Indicator Heartbeat | Async background task emitting `send_chat_action(ChatAction.TYPING)` every 4 seconds during tool/LLM latency. | Chat ID, async cancellation token. | Active "typing..." visual feedback in user's Telegram client. | Silently swallows transient network errors; terminates on response ready. | Telegram UX Best Practices |
| 14 | Telegram Bot | User Access Control (Whitelist Security) | Whitelist validation (`ALLOWED_TELEGRAM_USER_IDS`) preventing unauthorized public access to private Obsidian vault. | Inbound `Update.effective_user.id`. | Allowed access or immediate rejection log with 403 response. | Drops update and logs security warning if user ID not in whitelist. | Security Hardening Standard |
| 15 | Tool Interface | Obsidian Note Lookup Tool (`read_note`) | Agent tool to search, retrieve, and parse markdown files and YAML frontmatter from the local Obsidian vault. | `path` (relative file path), optional `section`. | Full note text content, metadata frontmatter, file modified date. | `FileNotFoundError` or directory traversal violation returned to LLM. | Obsidian Markdown Specs |
| 16 | Tool Interface | Obsidian Note Mutation Tool (`write_note`) | Agent tool to create, overwrite, append, or prepend notes in the Obsidian vault with automated folder creation. | `path`, `content`, `mode` (`append`, `prepend`, `overwrite`). | Confirmation payload with path, bytes written, and timestamp. | Read-only filesystem error or invalid path rejection returned to LLM. | Obsidian Vault Architecture |
| 17 | Tool Interface | Obsidian Vault Search Tool (`search_notes`) | Keyword and semantic search across note titles, contents, and tags (`#tag`). | `query` string, optional `tag`, `limit`. | List of matching notes with relative paths and relevant snippet context. | Empty match list returned to LLM if no results found. | Knowledge Base Retrieval Specs |
| 18 | Tool Interface | Remote Vault Sync Tool (`sync_vault`) | Agent action to trigger Git sync (pull remote changes, stage dirty notes, commit, push to remote repository). | Optional commit message prefix. | Sync summary (pulled commits, pushed commits, files changed). | Git merge conflict or auth failure returned with recovery suggestion. | Git Synchronization Engine Specs |

---

### Edge Cases
| # | Feature | Input | Observed / Specified Behavior |
|---|---------|-------|-------------------------------|
| 1 | Message Chunking | LLM outputs a 9,000-character note analysis containing nested code blocks. | Chunker splits into 3 sequential Telegram messages at paragraph boundaries (`\n\n`), ensuring code block backticks ` ``` ` are properly closed and reopened across chunks. |
| 2 | Markdown Escaping | LLM generates text with unescaped special characters (e.g. `Price: $10.50 (incl. tax) - [Active]!`). | Formatter detects MarkdownV2 special characters (`.`, `!`, `-`, `(`, `)`, `[`, `]`) and escapes them (`Price: \$10\.50 \(incl\. tax\) \- \[Active\]\!`) or sends via HTML mode to avoid `BadRequest: Can't parse entities`. |
| 3 | Tool Call Path Traversal | Malicious or hallucinated tool call: `read_note(path="../../etc/passwd")`. | Path sanitizer resolves path against `VAULT_ROOT`, detects escape outside root, rejects execution immediately, and returns error: `PermissionDenied: Path must remain within vault directory`. |
| 4 | Long-Running Agent Tool Execution | Hermes executes multi-step search, note reading, and note creation taking 15 seconds. | Background typing task sends `ChatAction.TYPING` every 4.0s; Telegram client continuously displays "typing..."; bot yields event loop to remain responsive. |
| 5 | Unauthorized Telegram User | Unknown Telegram user sends `/start` or `/note Secret`. | Security filter checks `update.effective_user.id in ALLOWED_USER_IDS`. Rejects request with: "⛔ Unauthorized: Access to this private assistant is restricted." Logs warning. |
| 6 | Simultaneous Rapid Messages | User sends 3 messages in rapid succession (within 500ms). | Per-chat async lock (`asyncio.Lock`) queues incoming requests sequentially per user to prevent concurrent Git write conflicts or race conditions on vault files. |
| 7 | LLM Provider Outage / 429 Rate Limit | Primary LLM Provider (e.g. OpenRouter / Groq) returns HTTP 429 Too Many Requests. | Provider adapter catches 429, attempts exponential backoff retry (up to 3 retries), and if exhausted, fails over to configured secondary fallback provider (e.g. Together AI / OpenAI). |
| 8 | Empty or Whitespace Note Creation | Tool call `write_note(path="Notes/blank.md", content="   ", mode="overwrite")`. | Validator rejects empty note creation and returns informative message to LLM to provide meaningful content. |
| 9 | Telegram Polling Drop Pending Updates | Bot restarts after being offline for 2 hours while messages accumulated in Telegram queue. | `run_polling(drop_pending_updates=True)` drops stale updates on startup to prevent massive replay bursts and old duplicate note writes. |
| 10 | Non-existent Note Lookup | Agent queries `read_note(path="Daily/2026-01-01.md")` which does not exist. | Returns structured tool error: `{"status": "error", "message": "Note 'Daily/2026-01-01.md' does not exist. Available notes in Daily/: [...]"}` allowing Hermes to self-correct. |

---

## 2. Detailed Architectural Specifications

### Scope 1: Agent Pipeline Design

#### 1.1 Hermes Model Capabilities & Prompt Engineering
NousResearch Hermes models (notably **Hermes 3** on Llama-3.1 8B/70B/405B and **Hermes 2 Pro**) provide state-of-the-art steerability, multi-step agentic reasoning, and native structured tool calling.

1. **Native ChatML Tool Schema**:
   Hermes 3 uses standard ChatML tokens with custom XML tags for tool declaration and execution:
   ```text
   <|im_start|>system
   You are an intelligent personal AI companion powered by OpenHuman and Hermes.
   You have direct access to the user's personal Obsidian knowledge base via tools.
   
   # Current Context
   - Current UTC Time: 2026-08-14 21:35:00
   - User Name: User
   
   # Available Tools
   <tools>
   {"type": "function", "function": {"name": "read_note", "description": "Read markdown content from Obsidian vault", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relative path to note, e.g. Daily/2026-08-14.md"}}, "required": ["path"]}}}
   {"type": "function", "function": {"name": "write_note", "description": "Write or append markdown content to a note in Obsidian vault", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relative note path"}}, "content": {"type": "string", "description": "Content in Markdown format"}, "mode": {"type": "string", "enum": ["append", "overwrite", "prepend"], "default": "append"}}, "required": ["path", "content"]}}}
   {"type": "function", "function": {"name": "search_notes", "description": "Search notes by keyword or tag in the vault", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Search keyword or phrase"}, "tag": {"type": "string", "description": "Optional tag filter e.g. #project"}}, "required": ["query"]}}}
   {"type": "function", "function": {"name": "sync_vault", "description": "Trigger remote Git synchronization for the Obsidian vault", "parameters": {"type": "object", "properties": {"commit_message": {"type": "string", "description": "Optional commit message"}}, "required": []}}}
   </tools>
   <|im_end|>
   ```

2. **Reasoning & Tool Invocation**:
   When Hermes decides to execute an action, it emits:
   ```xml
   <tool_call>
   {"name": "write_note", "arguments": {"path": "Daily/2026-08-14.md", "content": "- [ ] Buy groceries after work", "mode": "append"}}
   </tool_call>
   ```

3. **Tool Feedback & Synthesis**:
   The engine executes the local tool and injects the result:
   ```xml
   <|im_start|>user
   <tool_response>
   {"name": "write_note", "content": {"status": "success", "path": "Daily/2026-08-14.md", "bytes_written": 32}}
   </tool_response>
   <|im_end|>
   <|im_start|>assistant
   I've added "- [ ] Buy groceries after work" to your Daily Note for today (`Daily/2026-08-14.md`).
   <|im_end|>
   ```

#### 1.2 OpenHuman Integration Concepts
OpenHuman represents a human-centric personal companion paradigm with:
1. **Memory Tree / Obsidian Vault Mirroring**:
   - Instead of storing private user knowledge in an opaque proprietary vector database, OpenHuman treats the Obsidian Markdown Vault as the primary ground truth for memory.
   - Folders represent memory layers:
     - `Daily/` (Episodic memory: thoughts, daily logs, tasks).
     - `People/` (Entity memory: contacts, relationships, preferences).
     - `Projects/` (Working memory: active goals, milestones, roadmaps).
     - `Knowledge/` (Semantic memory: reference notes, bookmarks, literature).
     - `Profile.md` (Core persona & user preferences: tone, style, timezone).
2. **Split-Brain Orchestration Loop**:
   - **Reflex Router**: Checks if incoming message is a direct command (`/note`, `/sync`, `/status`) or simple chit-chat, avoiding unnecessary heavy multi-step tool calls.
   - **Deep Hermes Reasoning Core**: For queries requiring knowledge lookup, synthesis, schedule modifications, or multi-step vault updates, Hermes conducts multi-turn tool calling.
3. **Conversational Persona**:
   - Empathetic, proactive, and concise.
   - Avoids robotic boilerplate; speaks as a trusted companion who knows the user's ongoing projects and habits.

#### 1.3 Provider Adapters & Multi-Model Orchestration
To support flexible deployment across free-tier and commercial endpoints, the agent pipeline defines a unified async provider abstraction:

```python
class LLMProvider(ABC):
    @abstractmethod
    async def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        pass
```

Supported Providers:
- **OpenRouterProvider**: Default for NousResearch Hermes 3 (`nousresearch/hermes-3-llama-3.1-8b`, `nousresearch/hermes-3-llama-3.1-70b`).
- **GroqProvider**: Ultra-fast inference with `llama-3.1-8b-instant` or Hermes ports.
- **TogetherProvider**: Dedicated Hermes 2 / Hermes 3 hosting.
- **OllamaProvider / Local vLLM**: OpenAI-compatible local endpoints (`http://localhost:11434/v1`).
- **OpenAIProvider**: Compatible with standard OpenAI API endpoints.

Failover Architecture:
```
User Query -> Primary Provider (e.g. OpenRouter Hermes 3)
                 |
                 +-> [Success] -> Return Response
                 |
                 +-> [HTTP 429/500 Timeout] -> Retry (x2) with Backoff
                                                 |
                                                 +-> [Exhausted] -> Fallback Provider (e.g. Groq / Together)
```

---

### Scope 2: Telegram Bot Architecture

#### 2.1 Async Framework (`python-telegram-bot` v20+)
`python-telegram-bot` (v20.x+) is built from the ground up on `asyncio` and is the optimal framework for our architecture:
- Fully asynchronous request handling.
- Integrated `JobQueue` (via APScheduler) for periodic background tasks (e.g. auto-syncing vault every 30 minutes).
- Built-in typed update handlers: `CommandHandler`, `MessageHandler`, `CallbackQueryHandler`.
- Robust error handler pipeline: `app.add_error_handler(global_error_handler)`.

#### 2.2 Long-Polling vs Webhook in Free-Tier Cloud
| Dimension | Long-Polling (`run_polling`) | Webhook (`run_webhook`) |
|---|---|---|
| **Public IP / SSL Requirement** | None (connects outbound to Telegram servers) | Requires public HTTPS URL with valid SSL cert |
| **Port Forwarding / NAT** | Works behind any NAT/firewall | Requires open inbound port |
| **Setup Complexity** | Zero external config (just `BOT_TOKEN`) | Complex: DNS, reverse proxy, domain validation |
| **Free-Tier Compatibility (Render, Fly.io, Railway, Koyeb, HF)** | **Superior** — runs as background container/worker | Requires HTTP routing setup and awake web service |
| **Cold Starts** | Buffers updates on Telegram servers | Telegram drops/retries updates if container is asleep |
| **Recommendation** | **Primary Choice**: Long-polling with `drop_pending_updates=True` | Optional advanced mode |

*Note on Free-Tier Keepalive*: Many free-tier container platforms (like Render Free Web Service) sleep if no incoming HTTP requests arrive. To solve this, our bot can run a lightweight async HTTP server (using `aiohttp` or `FastAPI`) in parallel on `$PORT` serving a `/healthz` endpoint, allowing free uptime monitors (e.g., UptimeRobot, cron jobs) to keep the container awake.

#### 2.3 Command Handlers & Interaction Design
1. `/start`
   - Checks user whitelist.
   - Greets user with OpenHuman persona.
   - Displays brief system overview and Obsidian vault connection status.
2. `/help`
   - Displays formatted guide:
     - 📝 `/note [title] [content]` - Quick append to daily note or specific file.
     - 🔍 `/ask [query]` - Ask anything from your Obsidian knowledge base.
     - 🔄 `/sync` - Force bidirectional Git sync with remote Obsidian repository.
     - 📊 `/status` - View bot uptime, active model, vault file count, Git sync state.
3. `/note [title] [content]`
   - Fast-path note taker. If no title provided, appends timestamped bullet to today's Daily Note (`Daily/YYYY-MM-DD.md`).
4. `/ask [query]`
   - Direct query to the agent pipeline.
5. `/sync`
   - Triggers `sync_vault()` immediately, sends status update ("🔄 Syncing vault with remote..."), and edits message upon completion ("✅ Vault synced. 2 files pulled, 1 file pushed.").
6. `/status`
   - Returns a structured diagnostic report:
     - Bot: 🟢 Online (uptime: 4d 12h)
     - LLM: `nousresearch/hermes-3-llama-3.1-8b` via OpenRouter
     - Vault: 142 notes, Clean (Last synced: 3 mins ago)
7. `Natural Conversation (Default Text)`:
   - Handled via `MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)`.
   - Passes input to `AgentPipeline`, which decides whether to converse, query notes, or perform vault actions.

#### 2.4 Resilience, UX & Telegram Constraints
1. **Message Chunking (4096-character limit)**:
   - Telegram rejects any `sendMessage` payload exceeding 4,096 UTF-8 characters.
   - Our chunker algorithm:
     - Splits on double newline `\n\n` (paragraphs).
     - If a paragraph exceeds 4,000 chars, splits on single newline `\n`.
     - If still too long, splits on sentence punctuation (`. `, `! `, `? `).
     - Tracks open Markdown code blocks (```` ``` ````) and closes them at the chunk boundary, then re-opens them at the start of the next chunk.
2. **Safe Formatting & Entity Sanitization**:
   - Standard Telegram MarkdownV2 requires escaping `_ * [ ] ( ) ~ > # + - = | { } . !`.
   - Implement a safe parser that parses LLM markdown into HTML tags (`<b>`, `<i>`, `<code>`, `<pre>`) or uses a robust MarkdownV2 escaper with fallback to plain text if Telegram API returns `BadRequest: Can't parse entities`.
3. **Typing Indicator Heartbeat**:
   - `ChatAction.TYPING` displays "typing..." in the Telegram header but expires after 5 seconds.
   - An async background task runs:
     ```python
     async def typing_heartbeat(context, chat_id, stop_event):
         while not stop_event.is_set():
             try:
                 await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
             except Exception:
                 pass
             await asyncio.sleep(4.0)
     ```
4. **Security Whitelist (`ALLOWED_TELEGRAM_USER_IDS`)**:
   - Telegram bots are public by default; anyone with the `@handle` can send messages.
   - To protect the user's private Obsidian notes, a middleware/decorator rejects any `user_id` not listed in the environment variable `ALLOWED_TELEGRAM_USER_IDS=12345678,87654321`.

---

### Scope 3: Tool Execution & Action Interface

#### 3.1 Agent-to-Obsidian Tool Interface Definition
The agent pipeline exposes 5 core tools to Hermes:

```json
[
  {
    "name": "read_note",
    "description": "Read the contents and metadata of an Obsidian markdown note",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "Relative path to note, e.g. 'Daily/2026-08-14.md' or 'Projects/Agent.md'"
        }
      },
      "required": ["path"]
    }
  },
  {
    "name": "write_note",
    "description": "Create a new note or write/append/prepend content to an existing Obsidian note",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "Relative note path, e.g. 'Daily/2026-08-14.md'"
        },
        "content": {
          "type": "string",
          "description": "Markdown formatted content to write"
        },
        "mode": {
          "type": "string",
          "enum": ["append", "prepend", "overwrite"],
          "description": "Write mode. Default is 'append'."
        }
      },
      "required": ["path", "content"]
    }
  },
  {
    "name": "search_notes",
    "description": "Search notes across the Obsidian vault by keyword, phrase, or tag",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "Search keyword or text"
        },
        "tag": {
          "type": "string",
          "description": "Optional tag filter without '#' e.g. 'project'"
        },
        "limit": {
          "type": "integer",
          "description": "Max results to return (default 5)"
        }
      },
      "required": ["query"]
    }
  },
  {
    "name": "list_notes",
    "description": "List notes in a folder or list all directories in the vault",
    "parameters": {
      "type": "object",
      "properties": {
        "folder": {
          "type": "string",
          "description": "Subdirectory to inspect. Empty string for root."
        }
      }
    }
  },
  {
    "name": "sync_vault",
    "description": "Synchronize the local Obsidian vault with the remote Git repository",
    "parameters": {
      "type": "object",
      "properties": {
        "commit_message": {
          "type": "string",
          "description": "Optional Git commit message"
        }
      }
    }
  }
]
```

#### 3.2 End-to-End Interaction Flow

```
[ Telegram User ]
       |  (1) "What did I work on yesterday and add a reminder to finish the PR today"
       v
[ Telegram Handler ] 
       |  (2) Check Whitelist -> Start typing heartbeat task
       v
[ OpenHuman Context Aggregator ]
       |  (3) Assemble prompt: System Persona + Date/Time + Memory Context
       v
[ Hermes Reasoning Engine ]
       |  (4) LLM outputs <tool_call> read_note("Daily/2026-08-13.md")
       v
[ Tool Executor ]
       |  (5) Read file from Obsidian Vault Manager -> Returns Markdown content
       v
[ Hermes Reasoning Engine ]
       |  (6) LLM parses yesterday's notes, outputs <tool_call> write_note("Daily/2026-08-14.md", "- [ ] Finish the PR", "append")
       v
[ Tool Executor ]
       |  (7) Writes note -> Marks vault dirty -> Returns success
       v
[ Hermes Reasoning Engine ]
       |  (8) LLM generates final OpenHuman persona response
       v
[ Telegram Formatter & Chunker ]
       |  (9) Stops typing task -> Escapes entities -> Splits chunks if >4096 chars
       v
[ Telegram User ]
          (10) "Yesterday you worked on the Dockerfile refactor and API adapters.
                I've added '- [ ] Finish the PR' to your Daily Note for today!"
```

---

## 3. Five-Component Handoff Report

### 3.1 Observation
1. **Authoritative Sources**:
   - NousResearch Hermes 3 chat template and tool use specification: Hermes utilizes native ChatML XML blocks (`<tools>`, `<tool_call>`, `<tool_response>`) and supports standard OpenAI tool-calling JSON schema when served via OpenAI-compatible endpoints (OpenRouter, Together AI, vLLM, Groq, Ollama).
   - OpenHuman Architecture (TinyHumans.ai): Local-first personal AI framework integrating a Memory Tree, conversational persona, and an Obsidian-compatible markdown vault as primary external memory with split-brain reflex/reasoning orchestration.
   - Telegram Bot API Specification: Hard 4,096 character limit per message, 5-second expiration on `ChatAction.TYPING`, strict entity parsing rules for MarkdownV2 requiring character escaping, and long-polling (`getUpdates` / `run_polling`) as the most resilient method for free-tier cloud containers without public domain/port dependencies.
   - `ORIGINAL_REQUEST.md`: Requires continuously running agent system with OpenHuman & Hermes models, Telegram messaging, Obsidian vault read/write & Git sync, operating on a free-tier cloud platform.

2. **Interface Contracts Identified**:
   - `LLMProvider` interface for multi-model / multi-backend orchestration.
   - `TelegramBot` with async event loop, command dispatching, chunking, typing heartbeat, and user whitelist authorization.
   - `ObsidianVaultManager` and `ToolExecutor` for safe local markdown operations and Git sync actions.

### 3.2 Logic Chain
1. *Premise 1*: The bot must run on free-tier cloud platforms (e.g. Render, Fly.io, Railway, Hugging Face Spaces) where public static IPs, inbound port forwarding, and custom SSL certificates are either unavailable or complex to maintain.
   *Deduction 1*: Long-polling with `drop_pending_updates=True` via `python-telegram-bot` v20+ is the most reliable transport mechanism, combined with a lightweight HTTP `/healthz` server on `$PORT` to prevent container sleeping.

2. *Premise 2*: OpenHuman emphasizes human-centric personal memory, while Hermes 3 provides industry-leading open-weights tool calling, steerability, and structured JSON output.
   *Deduction 2*: Integrating OpenHuman's memory hierarchy (mapping directly to Obsidian folders: Daily, Projects, People, Knowledge) with Hermes 3's tool-calling loop produces a seamless, privacy-preserving personal agent.

3. *Premise 3*: Telegram rejects messages over 4,096 characters and throws exceptions on unescaped MarkdownV2 characters.
   *Deduction 3*: The Telegram output pipeline must include a boundary-aware chunker (preserving code blocks) and an entity sanitizer/HTML converter to guarantee zero dropped messages.

4. *Premise 4*: Tool execution must interact with a real or mock Obsidian vault directory and execute Git operations.
   *Deduction 4*: A clean separation between `ToolExecutor` (validation, path sanitization, traversal prevention) and `ObsidianVaultManager` (file I/O, frontmatter parsing, Git sync) enables high testability (unit tests with mock vaults and E2E integration tests with real Git remotes).

### 3.3 Caveats
1. **Model Context Window & Token Consumption**: When querying extensive Obsidian vaults, naive dumping of multiple large markdown notes can exceed LLM context windows or free-tier API rate limits. Retrieval must employ snippet extraction, line limits, or keyword/tag filtering.
2. **Concurrent User Requests**: If multiple messages arrive in quick succession from the user, simultaneous file writes to the same daily note could cause race conditions or merge conflicts. A per-chat async lock (`asyncio.Lock`) is mandatory.
3. **Telegram MarkdownV2 Complexity**: Raw LLM markdown often contains standalone characters like `_`, `*`, `.` or `!` that break Telegram MarkdownV2 parsers. Using HTML mode (`ParseMode.HTML`) with standard HTML tag conversion is significantly more robust than raw regex escaping of MarkdownV2.

### 3.4 Conclusion
The core agent pipeline and Telegram bot architecture are fully specified:
- **Agent Framework**: Dual-layer architecture combining OpenHuman persona/memory indexing with Hermes 3 reasoning & tool use, abstracted via a multi-provider async `LLMProvider` interface.
- **Telegram Bot**: Asynchronous `python-telegram-bot` v20+ bot running in long-polling mode, with command routing (`/start`, `/help`, `/note`, `/sync`, `/status`, `/ask`), natural conversation pipeline, typing heartbeat, smart chunking (<4096 chars), HTML/Markdown sanitization, and whitelist security.
- **Tool Interface**: Standardized JSON tool schema for `read_note`, `write_note`, `search_notes`, `list_notes`, and `sync_vault` with path-traversal protection and structured error handling.

### 3.5 Verification Method
To independently verify this specification:
1. **Mock Telegram Pipeline Test**:
   ```bash
   pytest tests/test_telegram_pipeline.py -v
   ```
   *Verifies*: Mock Telegram update received -> routed to agent pipeline -> tool executed -> formatted chunked response generated.
2. **Hermes Tool Calling & Provider Test**:
   ```bash
   pytest tests/test_llm_providers.py -v
   ```
   *Verifies*: Provider adapter parses tool definitions, handles tool call outputs, formats `<tool_response>` ChatML and OpenAI JSON schema, and executes failover logic.
3. **Obsidian Tool Execution Test**:
   ```bash
   pytest tests/test_obsidian_tools.py -v
   ```
   *Verifies*: `read_note`, `write_note` (append/prepend/overwrite), `search_notes`, and path traversal rejection (`../../`).
