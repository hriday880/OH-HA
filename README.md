# OpenHuman & Hermes Telegram Companion with Obsidian Knowledge Base & Cloud Deployment

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Multi-Stage](https://img.shields.io/badge/docker-multi--stage-green.svg)](deploy/Dockerfile)
[![Test Suite](https://img.shields.io/badge/tests-100%25%20passing-brightgreen.svg)](#running-the-test-suite)

An autonomous, continuously running personal AI companion that interfaces with users via **Telegram**, maintains a persistent second brain inside an **Obsidian Markdown Vault** with bidirectional remote **Git synchronization**, and operates reliably within free-tier cloud container constraints (256MB–512MB RAM, ephemeral storage).

---

## Architecture Overview

The system combines OpenHuman persona mapping and Hermes multi-step tool-use reasoning into a split-brain architecture, coupled with an aiohttp keepalive health server and a resilient Git synchronization engine:

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
                                     | (HTTPS PAT / SSH Keys)
                                     v
                       +---------------------------+
                       | Remote Git Repository     |
                       | (GitHub / GitLab / Gitea) |
                       | User's Obsidian Vault     |
                       +---------------------------+
```

---

## Core Capabilities

1. **Split-Brain Intelligence**:
   - **Fast-Path Reflex**: Immediate handling of slash commands (`/start`, `/note`, `/sync`, `/status`, `/ask`) and direct note capture.
   - **Hermes Deep Reasoning**: Multi-step tool-calling loop using ChatML XML formatting (`<tools>`, `<tool_call>`, `<tool_response>`) and JSON tool schemas.
   - **OpenHuman Memory**: Context injection from persona guidelines and vault folders (`User_Profile/`, `Evergreen/`, `Conversations/`).

2. **Obsidian Vault Knowledge Base**:
   - Full YAML frontmatter parser and serializer.
   - Note CRUD operations (create, read, append, prepend, list).
   - `[[Wikilink]]` and alias parser with bidirectional backlink graph resolution.
   - SQLite FTS5 BM25 full-text search with hierarchical `#tag` indexing.
   - Strict path traversal protection (enforces `.md` extensions and blocks directory escapes).

3. **Remote Git Synchronization**:
   - Secure HTTPS Personal Access Token (PAT) and SSH deploy key authentication without log leakage.
   - Auto-stashing of dirty local changes prior to pull/rebase.
   - Debounced commit queue to batch rapid updates.
   - Non-destructive merge conflict resolution: forks conflicting agent edits to separate conflict notes to protect user edits.

4. **Production Telegram Bot UX**:
   - Long-polling lifecycle with `drop_pending_updates=True`.
   - Automatic message chunking (<= 4096 characters) with HTML tag sanitization.
   - Interactive typing heartbeat indicator during multi-step reasoning.
   - Fail-safe user whitelist security middleware.

5. **Cloud-Hardened Container Runtime**:
   - Multi-stage Debian slim build (`python:3.11-slim-bookworm`).
   - Unprivileged non-root user (`botuser`, UID 10001).
   - `tini` as PID 1 init process to cleanly reap zombie processes and trap `SIGTERM`/`SIGINT`.
   - Low-memory glibc optimization (`MALLOC_ARENA_MAX=2`) preventing heap fragmentation on 256MB-512MB RAM containers.
   - Built-in `HEALTHCHECK` probing `GET /health`.

---

## Telegram Bot Setup

1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts to choose a bot name and username (e.g., `my_companion_hermes_bot`).
3. Copy the generated **HTTP API Token** (e.g., `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).
4. Find your numeric Telegram User ID:
   - Message [@userinfobot](https://t.me/userinfobot) or check the bot logs when sending an initial message.
   - Configure this ID in `ALLOWED_TELEGRAM_USER_IDS` to restrict access exclusively to you.

---

## Obsidian Vault Remote Git Setup

To synchronize notes between your desktop/mobile Obsidian app and the cloud bot:

1. Create a private repository on GitHub, GitLab, or Gitea (e.g., `my-obsidian-vault`).
2. Generate an access credential:
   - **HTTPS PAT (Recommended)**: Create a Personal Access Token with `repo` read/write permissions.
   - **SSH Deploy Key**: Generate an SSH key pair (`ssh-keygen -t ed25519 -C "bot@openhuman"`) and add the public key with write access to the repository Deploy Keys.
3. In Obsidian (Desktop/Mobile), install the **Obsidian Git** community plugin to enable seamless automatic sync on your local devices.

---

## Local Development & Setup

### 1. Clone & Environment Configuration

```bash
# Clone the repository
git clone https://github.com/your-username/openhuman-hermes-bot.git
cd openhuman-hermes-bot

# Create and activate Python 3.11+ virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy environment configuration
cp deploy/.env.example .env
```

### 2. Configure `.env`

Edit `.env` with your actual credentials:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ALLOWED_TELEGRAM_USER_IDS=123456789
LLM_PROVIDER=openrouter
LLM_MODEL=nousresearch/hermes-3-llama-3.1-8b
LLM_API_KEY=your_openrouter_api_key
GIT_REMOTE_URL=https://github.com/username/my-obsidian-vault.git
GIT_AUTH_TOKEN=your_github_pat_token
VAULT_PATH=./vault
PORT=8080
ENVIRONMENT=development
```

### 3. Run Locally

```bash
python -m bot.main
```

---

## Running the Test Suite

The project includes an exhaustive 5-tier test suite covering unit features, boundary constraints, pairwise integrations, end-to-end acceptance criteria (AC 1–4), and adversarial security audits:

```bash
# Run the entire test suite
pytest -v

# Run Milestone 5 / Containerization & Blueprint tests
pytest tests/tier1_feature/test_f20_dockerfile_runtime.py tests/tier1_feature/test_f21_deployment_blueprints.py tests/tier4_application/test_ac3_dockerfile_validation.py -v

# Run Acceptance Criteria (Tiers 1-4)
pytest tests/tier4_application/ -v

# Run Adversarial & Security Tests (Tier 5)
pytest tests/tier5_adversarial/ -v
```

---

## Free-Tier Cloud Deployment Guide

The companion is optimized to run 24/7 on free-tier container platforms with zero paid infrastructure.

### Option A: Render (Free Web Service)

Render provides free Docker web services with automatic TLS and keepalive health probes.

1. Push your repository to GitHub or GitLab.
2. Sign in to [Render](https://render.com) and click **New +** → **Blueprint**.
3. Select your repository. Render will automatically parse `deploy/render.yaml`.
4. Fill in the secret environment variables in the Render Dashboard:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot API Token.
   - `ALLOWED_TELEGRAM_USER_IDS`: Your Telegram numeric User ID.
   - `LLM_API_KEY`: Your OpenRouter/Groq API Key.
   - `GIT_REMOTE_URL`: Your Obsidian GitHub repository URL.
   - `GIT_AUTH_TOKEN`: Your GitHub PAT.
5. Click **Apply**. Render will build the multi-stage Dockerfile and start the daemon.

---

### Option B: Fly.io (Free MicroVM)

Fly.io offers free-tier `shared-cpu-1x` machines with 256MB RAM.

1. Install the Fly CLI:
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```
2. Log in and launch the application:
   ```bash
   flyctl auth login
   flyctl launch --config deploy/fly.toml --no-deploy
   ```
3. Set secrets:
   ```bash
   flyctl secrets set \
     TELEGRAM_BOT_TOKEN="your_telegram_token" \
     ALLOWED_TELEGRAM_USER_IDS="123456789" \
     LLM_API_KEY="your_llm_api_key" \
     GIT_REMOTE_URL="https://github.com/username/my-obsidian-vault.git" \
     GIT_AUTH_TOKEN="your_git_pat"
   ```
4. Deploy:
   ```bash
   flyctl deploy --config deploy/fly.toml
   ```

---

### Option C: Koyeb (Free Serverless Container)

1. Sign up at [Koyeb](https://www.koyeb.com).
2. Create a **New App** → Select **GitHub**.
3. Set **Build type** to `Dockerfile` and specify path `deploy/Dockerfile`.
4. Configure environment variables matching `.env.example`.
5. Set Health Check path to `/health` on port `8080`.
6. Click **Deploy**.

---

### Option D: Hugging Face Spaces (Docker Space)

1. Create a new Space on [Hugging Face](https://huggingface.co/spaces) with **SDK: Docker**.
2. Push this repository to your Space repository.
3. In **Settings** → **Variables and secrets**, add your environment variables (`TELEGRAM_BOT_TOKEN`, `ALLOWED_TELEGRAM_USER_IDS`, `LLM_API_KEY`, `GIT_REMOTE_URL`, `GIT_AUTH_TOKEN`, `PORT=7860`).
4. Hugging Face Spaces will automatically build the container and maintain uptime.

---

### Option E: Docker Compose / VPS (Self-Hosted)

For running on a local server, Raspberry Pi, or unmanaged VPS:

```bash
# Build and run in background
docker compose -f deploy/docker-compose.yml up -d --build

# View container logs
docker compose -f deploy/docker-compose.yml logs -f

# Stop container
docker compose -f deploy/docker-compose.yml down
```

---

## Free-Tier Keepalive & Health Monitoring

Free-tier providers (such as Render) spin down inactive containers after 15 minutes of HTTP inactivity. The application provides an integrated lightweight `aiohttp` HTTP server that exposes `/health` and `/metrics`:

- `GET /health` returns:
  ```json
  {
    "status": "healthy",
    "timestamp": "2026-08-15T05:30:00Z",
    "bot_running": true,
    "git_synced": true,
    "uptime_seconds": 3600
  }
  ```

- `GET /metrics` returns:
  ```json
  {
    "messages_processed": 42,
    "tool_calls_executed": 18,
    "git_syncs_completed": 6,
    "last_sync_timestamp": "2026-08-15T05:00:00Z"
  }
  ```

### Setting up Keepalive Pings:
Use any free monitoring service to ping your public container URL every 10–14 minutes:
- [UptimeRobot](https://uptimerobot.com) (HTTP monitor for `https://<your-app>.onrender.com/health`)
- [Cron-Job.org](https://cron-job.org)
- [Better Stack / Uptime](https://betterstack.com)

---

## Bot Commands Reference

| Command | Description | Example |
| :--- | :--- | :--- |
| `/start` | Welcome message and system status overview | `/start` |
| `/help` | Detailed help menu with available commands and features | `/help` |
| `/note <content>` | Instantly capture a quick note or append to today's daily log | `/note Meeting with Alice at 3pm #meetings` |
| `/sync` | Manually trigger bidirectional Git pull, rebase, and push | `/sync` |
| `/status` | View container health, uptime, memory, and sync status | `/status` |
| `/ask <query>` | Query the vault knowledge base using hybrid FTS5 and Hermes reasoning | `/ask What did I discuss regarding project roadmap?` |

*Natural conversation:* Any plain text message sent to the bot will be processed through the OpenHuman persona memory and Hermes tool-use pipeline to read, update, or synthesize notes from your Obsidian vault.

---

## Memory Optimization & Hardening

To ensure stable execution inside 256MB–512MB RAM constraints:
- **`MALLOC_ARENA_MAX=2`**: Limits glibc memory arenas to prevent virtual memory fragmentation.
- **Debounced Git Sync**: Coalesces rapid note updates into batch commits to minimize disk I/O and subprocess spawning.
- **SQLite FTS5 Indexes**: Stored in a lightweight SQLite index file (`vault/.search_index.db`) for sub-millisecond keyword and tag queries with minimal RAM footprint.
- **Secret Scrubbing**: Automatic credential masking (`ghp_***xyz`) across all application logs and exceptions.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
