"""
Shared Test Fixtures for OpenHuman & Hermes Agent Testing.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator

from bot.config import Config
from bot.agent.providers import MockLLMProvider
from bot.agent.tools import ToolRegistry, STANDARD_OBSIDIAN_TOOLS
from bot.agent.persona import MemoryTreeContext, OpenHumanPersona
from bot.agent.pipeline import SplitBrainAgentPipeline


import pytest

# Ensure isolated hermetic git execution in all tests
os.environ["GIT_CONFIG_GLOBAL"] = "/dev/null"
os.environ["GIT_CONFIG_SYSTEM"] = "/dev/null"
os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
os.environ["GIT_AUTHOR_NAME"] = "Test Agent"
os.environ["GIT_AUTHOR_EMAIL"] = "agent@test.local"
os.environ["GIT_COMMITTER_NAME"] = "Test Agent"
os.environ["GIT_COMMITTER_EMAIL"] = "agent@test.local"


def create_temp_vault() -> Path:
    """Create a populated temporary Obsidian vault for testing."""
    temp_dir = Path(tempfile.mkdtemp(prefix="obsidian_vault_test_"))

    # Create directory structure
    (temp_dir / "Daily").mkdir(parents=True, exist_ok=True)
    (temp_dir / "10-daily").mkdir(parents=True, exist_ok=True)
    (temp_dir / "Projects").mkdir(parents=True, exist_ok=True)
    (temp_dir / "40-projects").mkdir(parents=True, exist_ok=True)
    (temp_dir / "Knowledge").mkdir(parents=True, exist_ok=True)
    (temp_dir / "50-knowledge").mkdir(parents=True, exist_ok=True)
    (temp_dir / "People").mkdir(parents=True, exist_ok=True)
    (temp_dir / "00-index").mkdir(parents=True, exist_ok=True)

    # Populate Profile.md
    profile_content = """---
user: TestUser
timezone: UTC
focus: AI Agents & Obsidian Knowledge Management
---
# User Profile
- Name: TestUser
- Preferences: Direct, concise responses with code examples.
"""
    (temp_dir / "Profile.md").write_text(profile_content, encoding="utf-8")

    # Populate Daily notes
    daily_m1_content = """---
date: 2026-08-14
tags: [daily, log]
---
# Daily Log: 2026-08-14
- [x] Refactored LLM provider adapters
- [ ] Implement split-brain reasoning loop
"""
    (temp_dir / "Daily" / "2026-08-14.md").write_text(daily_m1_content, encoding="utf-8")

    daily_m2_content = """---
title: "2026-08-14"
date: "2026-08-14"
tags:
  - daily-note
  - log
---
# 2026-08-14

## Log
- [x] Refactored LLM provider adapters
- [ ] Implement split-brain reasoning loop
"""
    (temp_dir / "10-daily" / "2026-08-14.md").write_text(daily_m2_content, encoding="utf-8")


    # Populate Project notes
    project_content = """---
title: Hermes Agent Pipeline
status: active
tags: [project, agent]
---
# Project: Hermes Agent Pipeline
Multi-step reasoning engine with tool execution dispatch.
"""
    (temp_dir / "Projects" / "HermesAgent.md").write_text(project_content, encoding="utf-8")

    apollo_content = """---
title: "Project Apollo"
status: "active"
tags:
  - project/apollo
  - priority/high
aliases:
  - "Apollo"
created: 2026-08-15T00:00:00Z
---
# Project Apollo

Autonomous cloud companion note engine.
See [[Quantum Computing Basics]] for quantum principles.
"""
    (temp_dir / "40-projects" / "Project_Apollo.md").write_text(apollo_content, encoding="utf-8")

    quantum_content = """---
title: "Quantum Computing Basics"
tags:
  - science/quantum
  - physics
aliases:
  - "Quantum Computing"
---
# Quantum Computing Basics

Principles of superposition and quantum entanglement in computation.
"""
    (temp_dir / "50-knowledge" / "Quantum_Computing.md").write_text(quantum_content, encoding="utf-8")

    moc_content = """---
title: "Vault MOC Index"
tags:
  - index
  - moc
---
# Map of Content Index

- [[Project Apollo]]
- [[Quantum Computing Basics]]
"""
    (temp_dir / "00-index" / "MOC_Index.md").write_text(moc_content, encoding="utf-8")

    return temp_dir


def cleanup_temp_vault(vault_path: Path) -> None:
    """Safely delete temporary vault directory."""
    if vault_path.exists() and vault_path.is_dir():
        shutil.rmtree(vault_path, ignore_errors=True)


@pytest.fixture
def mock_vault_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Pytest fixture providing a clean mock Obsidian vault directory."""
    vault = create_temp_vault()
    try:
        yield vault
    finally:
        cleanup_temp_vault(vault)


@pytest.fixture
def test_config(mock_vault_dir: Path) -> Config:
    """Pytest fixture for clean test configuration."""
    return Config(
        vault_path=mock_vault_dir,
        environment="test",
        llm_provider="mock",
        llm_model="mock-hermes-3-8b",
        max_reasoning_steps=5,
        allowed_telegram_user_ids=[12345, 67890, 123456789],
    )


@pytest.fixture
def mock_llm_provider() -> MockLLMProvider:
    """Pytest fixture for MockLLMProvider."""
    return MockLLMProvider()


class MockTelegramApp:
    """Mock Telegram application context for testing message dispatch."""

    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []
        self.sent_chat_actions: list[dict[str, Any]] = []

    async def send_message(self, chat_id: int, text: str, **kwargs: Any) -> dict[str, Any]:
        msg = {"chat_id": chat_id, "text": text, **kwargs}
        self.sent_messages.append(msg)
        return msg

    async def send_chat_action(self, chat_id: int, action: str, **kwargs: Any) -> bool:
        self.sent_chat_actions.append({"chat_id": chat_id, "action": action, **kwargs})
        return True

    @property
    def chat_actions(self) -> list[dict[str, Any]]:
        """Alias for sent_chat_actions."""
        return self.sent_chat_actions


@pytest.fixture
def mock_telegram_app() -> MockTelegramApp:
    """Pytest fixture providing a mock Telegram bot application context."""
    return MockTelegramApp()


@pytest.fixture
def aiohttp_client():
    """Pytest fixture providing an async HTTP client factory for aiohttp applications."""
    from aiohttp.test_utils import TestClient, TestServer
    clients = []

    async def _create_client(app: Any, **kwargs: Any) -> TestClient:
        client = TestClient(TestServer(app), **kwargs)
        await client.start_server()
        clients.append(client)
        return client

    return _create_client




@pytest.fixture
def bare_git_remote(tmp_path_factory: pytest.TempPathFactory) -> Generator[Path, None, None]:
    """Creates a temporary bare Git repository with an initial commit on 'main'."""
    import subprocess
    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_CONFIG_SYSTEM"] = "/dev/null"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_AUTHOR_NAME"] = "Test Init"
    env["GIT_AUTHOR_EMAIL"] = "init@test.local"
    env["GIT_COMMITTER_NAME"] = "Test Init"
    env["GIT_COMMITTER_EMAIL"] = "init@test.local"

    remote_dir = tmp_path_factory.mktemp("bare_remote.git")
    subprocess.run(["git", "init", "--bare", str(remote_dir)], check=True, capture_output=True, env=env)

    seed_dir = tmp_path_factory.mktemp("seed_repo")
    subprocess.run(["git", "init", str(seed_dir)], check=True, capture_output=True, env=env)
    subprocess.run(["git", "-C", str(seed_dir), "config", "user.name", "Test Init"], check=True, capture_output=True, env=env)
    subprocess.run(["git", "-C", str(seed_dir), "config", "user.email", "init@test.local"], check=True, capture_output=True, env=env)

    (seed_dir / "README.md").write_text("# Test Obsidian Vault\n", encoding="utf-8")
    (seed_dir / "00-inbox").mkdir(parents=True, exist_ok=True)
    (seed_dir / "00-inbox" / "welcome.md").write_text("# Welcome to Vault\n", encoding="utf-8")
    (seed_dir / "40-projects").mkdir(parents=True, exist_ok=True)
    (seed_dir / "40-projects" / "Project_Apollo.md").write_text("# Project Apollo\n", encoding="utf-8")
    (seed_dir / "10-daily").mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "-C", str(seed_dir), "add", "."], check=True, capture_output=True, env=env)
    subprocess.run(["git", "-C", str(seed_dir), "commit", "-m", "Initial vault commit"], check=True, capture_output=True, env=env)
    subprocess.run(["git", "-C", str(seed_dir), "branch", "-M", "main"], check=True, capture_output=True, env=env)
    subprocess.run(["git", "-C", str(seed_dir), "remote", "add", "origin", str(remote_dir)], check=True, capture_output=True, env=env)
    subprocess.run(["git", "-C", str(seed_dir), "push", "-u", "origin", "main"], check=True, capture_output=True, env=env)
    subprocess.run(["git", "--git-dir", str(remote_dir), "symbolic-ref", "HEAD", "refs/heads/main"], check=True, capture_output=True, env=env)

    yield remote_dir
    shutil.rmtree(remote_dir, ignore_errors=True)
    shutil.rmtree(seed_dir, ignore_errors=True)


@pytest.fixture
def mock_git_remote_and_clone(
    bare_git_remote: Path, tmp_path_factory: pytest.TempPathFactory
) -> Generator[tuple[Path, Path], None, None]:
    """Pytest fixture providing a bare remote and a cloned local repository."""
    import subprocess
    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_CONFIG_SYSTEM"] = "/dev/null"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_AUTHOR_NAME"] = "Test Agent"
    env["GIT_AUTHOR_EMAIL"] = "agent@test.local"
    env["GIT_COMMITTER_NAME"] = "Test Agent"
    env["GIT_COMMITTER_EMAIL"] = "agent@test.local"

    run_dir = tmp_path_factory.mktemp("clone_session")
    local_dir = run_dir / "local_clone"
    subprocess.run(["git", "clone", str(bare_git_remote), str(local_dir)], check=True, capture_output=True, env=env)
    subprocess.run(["git", "-C", str(local_dir), "config", "user.name", "Test Agent"], check=True, capture_output=True, env=env)
    subprocess.run(["git", "-C", str(local_dir), "config", "user.email", "agent@test.local"], check=True, capture_output=True, env=env)

    yield bare_git_remote, local_dir
    shutil.rmtree(run_dir, ignore_errors=True)




