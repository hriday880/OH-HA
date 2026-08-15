# BRIEFING — 2026-08-14T21:35:00Z

## Mission
Survey, probe, and specify the Core Agent Pipeline (OpenHuman & Hermes models, multi-model orchestration, provider adapters) and Telegram Bot Architecture (async bot framework, command/chat routing, chunking, typing indicators, rate-limiting, and Obsidian tool execution interface) for free-tier cloud deployment.

## 🔒 My Identity
- Archetype: spec_miner
- Roles: Teamwork specialist, Specification Miner
- Working directory: /Users/hriday/Documents/OH and HA/.agents/teamwork_preview_spec_miner_survey_1
- Original parent: 32cc2484-3047-421e-bf6d-877e479489cb
- Milestone: Step 0 (Survey Track - Explorer 1)

## 🔒 Key Constraints
- Purely discover, probe, and specify requirements and architectures; do not implement application code.
- Must cover Hermes 2/3 function calling / tool calling / structured output / ChatML formatting.
- Must cover OpenHuman persona/memory/agent loop integration concepts.
- Must cover Telegram async architecture (python-telegram-bot vs aiogram, long-polling vs webhooks, commands, error handling, rate limiting).
- Must define tool execution and routing interface between Telegram bot and Obsidian manager.
- Output handoff report to `handoff.md` with the 5 required components and specification tables.

## Current Parent
- Conversation ID: 32cc2484-3047-421e-bf6d-877e479489cb
- Updated: 2026-08-14T21:35:00Z

## Task Summary
- **What to build**: Comprehensive architecture specification for Agent Pipeline (OpenHuman + Hermes) and Telegram Bot Integration.
- **Success criteria**: Full feature discovery table, edge cases table, detailed interface and architecture specifications for the agent loop, model provider adapters, bot handlers, and tool calling interface.
- **Interface contracts**: `/Users/hriday/Documents/OH and HA/.agents/teamwork_preview_spec_miner_survey_1/handoff.md`

## Key Decisions Made
- Specified Hermes 3 ChatML XML tool-calling and OpenAI-compatible tool calling schemas.
- Specified OpenHuman memory tree architecture with Obsidian vault folder mapping (Daily, People, Projects, Knowledge, Profile).
- Selected `python-telegram-bot` v20+ with long-polling (`drop_pending_updates=True`) and parallel lightweight HTTP `/healthz` server on `$PORT` for free-tier cloud deployment.
- Specified 4096-char boundary-aware chunker, HTML/MarkdownV2 entity sanitization, 4.0s typing heartbeat loop, and whitelist user security (`ALLOWED_TELEGRAM_USER_IDS`).
- Specified 5 core Obsidian tools (`read_note`, `write_note`, `search_notes`, `list_notes`, `sync_vault`) with path traversal guards.

## Artifact Index
- `/Users/hriday/Documents/OH and HA/.agents/teamwork_preview_spec_miner_survey_1/handoff.md` — Comprehensive survey & specification report.
- `/Users/hriday/Documents/OH and HA/.agents/teamwork_preview_spec_miner_survey_1/DISPATCH.md` — Dispatch log.
- `/Users/hriday/Documents/OH and HA/.agents/teamwork_preview_spec_miner_survey_1/progress.md` — Progress tracker.
