## 2026-08-14T21:32:24Z
You are teamwork_preview_worker_m1_1 (Implementation Track - Milestone 1 Worker).
Your Working Directory: /Users/hriday/Documents/OH and HA/.agents/teamwork_preview_worker_m1_1
Authoritative User Request: /Users/hriday/Documents/OH and HA/.agents/ORIGINAL_REQUEST.md
Project Blueprint: /Users/hriday/Documents/OH and HA/PROJECT.md
Test Infra Blueprint: /Users/hriday/Documents/OH and HA/TEST_INFRA.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Objective:
Implement Milestone 1: Core Configuration, LLM Provider Adapters (Hermes / OpenHuman), Prompts, Tools Registry, Persona Context Builder, and Split-Brain Agent Pipeline.

Specific Scope & Owned Files:
1. You exclusively own:
   - `bot/__init__.py`
   - `bot/config.py` (Pydantic / dataclass configuration, environment variable loading, default values, secret masking, validation)
   - `bot/agent/__init__.py`
   - `bot/agent/providers.py` (BaseLLMProvider, OpenRouterProvider, GroqProvider, TogetherProvider, OllamaProvider, MockLLMProvider with tool calling and retry/backoff)
   - `bot/agent/prompts.py` (Hermes 3 ChatML XML tool prompts `<tools>`, `<tool_call>`, `<tool_response>`, OpenHuman system prompts)
   - `bot/agent/tools.py` (ToolDefinition, ToolRegistry, standard tool schemas for `read_note`, `write_note`, `search_notes`, `list_notes`, `sync_vault`, execution dispatch)
   - `bot/agent/persona.py` (OpenHuman persona management, memory tree context builder from vault paths)
   - `bot/agent/pipeline.py` (SplitBrainAgentPipeline: fast triage + deep multi-step Hermes reasoning tool execution loop)
   - `requirements.txt` & `requirements-dev.txt` (Core dependencies: pydantic, pydantic-settings, httpx, python-telegram-bot, aiohttp, pyyaml, gitpython, pytest, pytest-asyncio, etc.)
2. Implement clean, robust, fully typed Python code with thorough error handling and docstrings.
3. Test your implementation using pytest or direct test runs.
4. Document all implemented classes, methods, and verification results in `/Users/hriday/Documents/OH and HA/.agents/teamwork_preview_worker_m1_1/handoff.md`.
5. Send a message back when complete.
