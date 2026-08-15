# E2E Test Infra: OpenHuman & Hermes Telegram Agent with Obsidian Sync

## Test Philosophy
- **Opaque-Box & Requirement-Driven**: Derived strictly from `ORIGINAL_REQUEST.md` and user specifications, not internal implementation quirks.
- **Methodology**: 4-Tier Multi-Method Testing (Category-Partition + Boundary Value Analysis + Pairwise Combinations + Real-World Workload Scenarios).
- **Core Acceptance Criteria Covered**:
  1. AC 1: Mock Telegram message -> agent pipeline -> generated response.
  2. AC 2: Reading sample notes from Obsidian vault directory and writing new notes.
  3. AC 3: Dockerfile build validation and container environment health.
  4. AC 4: Remote repository sync simulation (pull updates from and push changes to remote Obsidian repo).

## Feature Inventory & Test Mapping
| # | Feature | Source | Tier 1 (Count) | Tier 2 (Count) | Tier 3 | Tier 4 |
|---|---------|--------|:--------------:|:--------------:|:------:|:------:|
| 1 | Configuration & Env Validation | Survey 1,3 | >=5 | >=5 | ✓ | ✓ |
| 2 | LLM Provider Adapters | Survey 1 | >=5 | >=5 | ✓ | ✓ |
| 3 | Hermes Tool Calling & Prompt Engine | Survey 1 | >=5 | >=5 | ✓ | ✓ |
| 4 | OpenHuman Persona & Memory Tree | Survey 1,2 | >=5 | >=5 | ✓ | ✓ |
| 5 | Split-Brain Reflex & Intent Router | Survey 1 | >=5 | >=5 | ✓ | ✓ |
| 6 | Obsidian Frontmatter & Markdown Engine | Survey 2 | >=5 | >=5 | ✓ | ✓ |
| 7 | Path Normalization & Traversal Security | Survey 1,2 | >=5 | >=5 | ✓ | ✓ |
| 8 | Obsidian Note CRUD & Archetypes | Survey 2 | >=5 | >=5 | ✓ | ✓ |
| 9 | Wikilink & Backlink Engine | Survey 2 | >=5 | >=5 | ✓ | ✓ |
| 10 | Hybrid Search & Tag Indexing | Survey 2 | >=5 | >=5 | ✓ | ✓ |
| 11 | Git Repo Lifecycle & Auth | Survey 2,3 | >=5 | >=5 | ✓ | ✓ |
| 12 | Bidirectional Pull/Rebase & Stash | Survey 2,3 | >=5 | >=5 | ✓ | ✓ |
| 13 | Debounced Commit & Push Engine | Survey 2,3 | >=5 | >=5 | ✓ | ✓ |
| 14 | Non-Destructive Conflict Resolution | Survey 2,3 | >=5 | >=5 | ✓ | ✓ |
| 15 | Telegram Async Bot Lifecycle | Survey 1,3 | >=5 | >=5 | ✓ | ✓ |
| 16 | Telegram Commands & Routing | Survey 1 | >=5 | >=5 | ✓ | ✓ |
| 17 | UX Resilience & Security Whitelist | Survey 1 | >=5 | >=5 | ✓ | ✓ |
| 18 | HTTP Health & Keepalive Server | Survey 3 | >=5 | >=5 | ✓ | ✓ |
| 19 | Continuous Daemon & Graceful Shutdown | Survey 3 | >=5 | >=5 | ✓ | ✓ |
| 20 | Multi-Stage Docker Build & Runtime | Survey 3 | >=5 | >=5 | ✓ | ✓ |
| 21 | Free-Tier Deployment Blueprints | Survey 3 | >=5 | >=5 | ✓ | ✓ |

## Test Architecture
- **Framework**: `pytest`, `pytest-asyncio`
- **Fixtures (`tests/conftest.py`)**:
  - `mock_vault_dir`: Temporary directory populated with sample Obsidian markdown notes, templates, and frontmatter.
  - `bare_git_remote`: Local bare git repository (`git init --bare`) acting as the mock GitHub/GitLab remote Obsidian vault.
  - `mock_llm_provider`: Deterministic test provider simulating Hermes tool calling, natural language generation, and multi-turn conversations.
  - `mock_telegram_app`: Mock Telegram application context for feeding synthetic updates and asserting outgoing messages and chat actions.
  - `test_config`: Clean configuration loaded with test defaults.
- **Directory Layout**:
  - `tests/tier1_feature/`: Component-level unit & functional tests in isolation.
  - `tests/tier2_boundary/`: Edge cases, bad inputs, timeouts, rate limits, path traversal attacks, dirty Git rebases, malformed YAML.
  - `tests/tier3_pairwise/`: Multi-component interactions (Telegram + LLM + Vault + Git sync).
  - `tests/tier4_application/`: Real-world end-to-end integration workflows matching AC 1-4.
  - `tests/tier5_adversarial/`: White-box adversarial testing, fuzzing, and security audits.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Acceptance Criteria | Features Exercised |
|---|----------|---------------------|--------------------|
| 1 | `test_ac1_telegram_to_agent_response` | AC 1 | Ingest mock Telegram message -> Route via OpenHuman/Hermes -> Generate contextual response with typing indicator |
| 2 | `test_ac2_obsidian_vault_read_and_write` | AC 2 | Read existing note from vault -> Extract frontmatter & body -> Write new note / append daily log -> Verify disk state |
| 3 | `test_ac3_dockerfile_build_validation` | AC 3 | Validate Dockerfile syntax, non-root user setup, healthcheck config, and dependencies installation |
| 4 | `test_ac4_remote_git_sync_simulation` | AC 4 | Initialize clone from bare remote -> Pull remote updates -> Agent writes new note -> Push changes -> Verify remote commit log |
| 5 | `test_e2e_full_conversation_and_vault_lifecycle` | AC 1, 2, 4 | Multi-turn Telegram dialogue -> Hermes searches vault -> Hermes writes conversation summary -> Git sync pushes to remote |
| 6 | `test_e2e_concurrent_conflict_resolution` | AC 4, Edge Case | Remote repo receives commit concurrently -> Agent writes local note -> Pull & rebase runs -> Conflict note cleanly forked |

## Minimum Thresholds
- Number of Features $N = 21$
- Tier 1: $\ge 5 \times 21 = 105$ tests
- Tier 2: $\ge 5 \times 21 = 105$ tests
- Tier 3: $\ge 21$ tests (pairwise cross-feature interactions)
- Tier 4: $\ge \max(5, 21 \div 2) = 11$ full application scenario tests
- **Total Minimum Test Count: $\ge 242$ tests**

## Execution Commands
```bash
# Run all tests
pytest tests/ -v

# Run specific tiers
pytest tests/tier1_feature/ -v
pytest tests/tier2_boundary/ -v
pytest tests/tier3_pairwise/ -v
pytest tests/tier4_application/ -v

# Run with coverage report
pytest --cov=bot --cov-report=term-missing tests/
```
