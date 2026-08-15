# Orchestration Plan: OpenHuman & Hermes Telegram Agent with Obsidian Sync

## Objective
Build, verify, and package a production-ready, continuously running Telegram bot agent system powered by OpenHuman and Hermes models, integrated with an Obsidian vault (read/write & remote Git sync) and containerized for free-tier cloud platforms.

## Tracks
1. **Survey Track (Step 0)**:
   - Explorer 1 (Spec Miner): Telegram Bot & Agent Pipeline specifications (OpenHuman / Hermes prompt architecture, message handling, command routing, streaming/async lifecycle).
   - Explorer 2 (Spec Miner): Obsidian Vault Management & Remote Git Sync architecture (markdown parsing, bidirectional sync, local staging, conflict handling, auth).
   - Explorer 3 (Spec Miner): Free-tier cloud deployment constraints, containerization (Dockerfile, entrypoints, health checks, environment config) and test architecture.

2. **Decomposition (Step 1 & 2A)**:
   - Create `PROJECT.md` and `TEST_INFRA.md`.
   - Dual-track structure:
     - **Track A: E2E Testing Track** (Test harness, mock Telegram, mock Obsidian Git remote, Docker validation, Tiers 1-4).
     - **Track B: Implementation Track**:
       - Milestone 1: Core Configuration, Logging, and OpenHuman/Hermes Agent Framework.
       - Milestone 2: Telegram Bot Integration & Interaction Pipeline.
       - Milestone 3: Obsidian Vault Manager & Remote Repository Sync Engine.
       - Milestone 4: Continuous Runner, Free-Tier Cloud Containerization & Deployment Scripts.
       - Milestone 5: Final E2E Test Suite Validation & Adversarial Hardening (Tier 5).

3. **Execution & Gate Verification**:
   - For each milestone: Explorer -> Worker -> Reviewers -> Challengers -> Forensic Auditor.
   - Strict gate pass criteria (build + test pass, 100% APPROVE, Challenger confirm, Auditor CLEAN).
