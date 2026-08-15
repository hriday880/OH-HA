# BRIEFING — 2026-08-15T03:01:20Z

## Mission
Investigate and specify the Free-Tier Cloud Deployment Strategy, Containerization, and Comprehensive Automated Testing Architecture for the OpenHuman & Hermes Telegram Agent with Obsidian Sync.

## 🔒 My Identity
- Archetype: spec_miner
- Roles: Specification Miner, Domain Expert (Cloud Deployment, Containerization, Test Harness)
- Working directory: /Users/hriday/Documents/OH and HA/.agents/teamwork_preview_spec_miner_survey_3
- Original parent: 32cc2484-3047-421e-bf6d-877e479489cb
- Milestone: Step 0 - Survey Track (Survey 3: Deployment & Test Architecture)

## 🔒 Key Constraints
- Must operate entirely within free-tier cloud platform constraints (RAM: 256MB-512MB, ephemeral storage with Git sync, 0-cost continuous or long-polling execution).
- Multi-stage Dockerfile with non-root security and minimal footprint (<150MB image, <100MB runtime memory).
- Testing suite must cover all acceptance criteria (Telegram mock pipeline, Obsidian vault read/write, Docker container build & healthcheck, Git sync pull/push).
- Strictly specification mining: do not implement production code, discover and specify full interface, behaviors, edge cases, and test harness design.

## Current Parent
- Conversation ID: 32cc2484-3047-421e-bf6d-877e479489cb
- Updated: 2026-08-15T03:01:20Z

## Task Summary
- **What to build**: Comprehensive specification report (`handoff.md`) covering free-tier cloud deployment architectures (Render, Fly.io, Koyeb, Railway, HF Spaces), containerization designs (Dockerfile, docker-compose, entrypoints, health checks), and automated test harness architecture (pytest tiers 1-4, mocks for Telegram/Git/Obsidian).
- **Success criteria**: Exhaustive technical analysis, detailed features discovered table, edge cases table, concrete Dockerfile/config templates, comprehensive test harness specification.
- **Interface contracts**: /Users/hriday/Documents/OH and HA/.agents/ORIGINAL_REQUEST.md
- **Code layout**: ~/teamwork_projects/openhuman_hermes_bot

## Key Decisions Made
- Standardized runtime base on `python:3.11-slim-bookworm` with `tini` for PID 1 signal management and non-root user `botuser` (UID 10001).
- Defined single-process async daemon model combining Telegram polling/webhook, `GET /health` HTTP server (port 8080), and Git sync manager.
- Formulated 4-Tier Pytest architecture with local bare Git remote fixtures (`git init --bare`) and synthetic Telegram update mocks ensuring 100% test independence from live cloud APIs.
- Specified concrete configuration files: `render.yaml`, `fly.toml`, `docker-compose.yml`, `.env.example`, and multi-stage `Dockerfile`.

## Artifact Index
- `.agents/teamwork_preview_spec_miner_survey_3/DISPATCH.md` — Dispatch log
- `.agents/teamwork_preview_spec_miner_survey_3/progress.md` — Liveness & step tracker
- `.agents/teamwork_preview_spec_miner_survey_3/handoff.md` — Authoritative Specification Mining Report
