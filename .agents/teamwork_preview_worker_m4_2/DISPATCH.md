## 2026-08-15T04:43:15Z
You are teamwork_preview_worker_m4_2 (Implementation Track - Milestone 4 Worker).
Your Working Directory: /Users/hriday/Documents/OH and HA/.agents/teamwork_preview_worker_m4_2
Authoritative User Request: /Users/hriday/Documents/OH and HA/.agents/ORIGINAL_REQUEST.md
Project Blueprint: /Users/hriday/Documents/OH and HA/PROJECT.md
Test Infra Blueprint: /Users/hriday/Documents/OH and HA/TEST_INFRA.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Objective:
Implement Milestone 4: Telegram Bot Integration, Commands, UX Sanitization, Unified HTTP Health Server, and Continuous Daemon with Graceful Shutdown.

Specific Scope & Owned Files:
1. You exclusively own:
   - `bot/telegram/__init__.py`
   - `bot/telegram/security.py` (User whitelist middleware / decorator verifying `ALLOWED_TELEGRAM_USER_IDS`, unauthorized access logging)
   - `bot/telegram/formatters.py` (Telegram message chunking <=4096 chars respecting code blocks and paragraphs, HTML and MarkdownV2 entity sanitizers)
   - `bot/telegram/commands.py` (Command handlers for `/start`, `/help`, `/note`, `/sync`, `/status`, `/ask` with typing indicator heartbeat)
   - `bot/telegram/bot.py` (TelegramBot: `python-telegram-bot` v20+ async lifecycle, long-polling with `drop_pending_updates=True`, natural conversation message router to `SplitBrainAgentPipeline`)
   - `bot/health.py` (Unified async HTTP server using `aiohttp` on `$PORT` serving `GET /health` and `GET /metrics` for free-tier keepalive monitors)
   - `bot/main.py` (Continuous Daemon entrypoint: co-schedules HTTP health server, Telegram bot, and periodic Git sync worker in single asyncio event loop; traps `SIGTERM`/`SIGINT` for graceful shutdown with in-flight request draining and final Git sync flush)
2. Interface alignment: Seamlessly integrate with `bot.agent.pipeline.SplitBrainAgentPipeline`, `bot.vault.manager.VaultManager`, `bot.git_sync.engine.GitSyncEngine`, and `bot.config.Config`.
3. Implement clean, robust, fully typed Python code with thorough error handling and docstrings.
4. Run unit and integration tests using pytest.
5. Document all implemented classes, methods, and verification results in `/Users/hriday/Documents/OH and HA/.agents/teamwork_preview_worker_m4_2/handoff.md`.
6. Send a message back when complete.
