## 2026-08-15T04:43:14Z

You are teamwork_preview_worker_m3_2 (Implementation Track - Milestone 3 Worker).
Your Working Directory: /Users/hriday/Documents/OH and HA/.agents/teamwork_preview_worker_m3_2
Authoritative User Request: /Users/hriday/Documents/OH and HA/.agents/ORIGINAL_REQUEST.md
Project Blueprint: /Users/hriday/Documents/OH and HA/PROJECT.md
Test Infra Blueprint: /Users/hriday/Documents/OH and HA/TEST_INFRA.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Objective:
Implement Milestone 3: Remote Git Synchronization Engine (Git repository lifecycle, clone, bidirectional pull & auto-stash rebase, debounced commit & push queue, HTTPS PAT / SSH deploy key auth, and non-destructive conflict note forking).

Specific Scope & Owned Files:
1. You exclusively own:
   - `bot/git_sync/__init__.py`
   - `bot/git_sync/auth.py` (HTTPS Personal Access Token auth helper, SSH deploy key setup with 0600 permissions, credential scrubbing in logs and exception traces)
   - `bot/git_sync/conflict.py` (Non-destructive conflict resolution: detects merge/rebase conflicts, preserves clean remote state, forks agent local modifications into `<Note> (Agent Conflict <timestamp>).md`, returns conflict report)
   - `bot/git_sync/engine.py` (GitSyncEngine: initialize_repo / clone, pull_and_rebase with auto-stash, commit_and_push with retry and backoff, debounced background sync worker, sync_now, get_status)
2. Interface alignment: Ensure `GitSyncEngine` cleanly integrates with `bot.vault.manager.VaultManager` and `bot.config.Config`.
3. Implement clean, robust, fully typed Python code with thorough error handling and docstrings.
4. Run unit and integration tests (including bare git remote simulation) using pytest.
5. Document all implemented classes, methods, and verification results in `/Users/hriday/Documents/OH and HA/.agents/teamwork_preview_worker_m3_2/handoff.md`.
6. Send a message back when complete.
