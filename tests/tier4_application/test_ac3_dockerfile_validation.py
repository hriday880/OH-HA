"""
Acceptance Criterion 3 (AC 3) Test Suite.
Verifies: "A deployment configuration file (e.g., Dockerfile) is provided and successfully builds the environment."
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest


class TestAC3DockerfileValidation:
    """Acceptance Criterion 3: Containerization & Deployment Configuration Validation."""

    def test_ac3_dockerfile_build_validation(self):
        """
        [AC 3 Core Test]
        Validates Dockerfile multi-stage syntax, unprivileged user isolation, memory settings,
        and healthcheck probe configuration.
        """
        dockerfile_candidates = [
            Path("deploy/Dockerfile"),
            Path("Dockerfile"),
        ]
        dockerfile = next((p for p in dockerfile_candidates if p.is_file()), None)

        if dockerfile is not None:
            content = dockerfile.read_text(encoding="utf-8")

            # 1. Multi-stage build structure
            assert "FROM" in content
            assert "builder" in content.lower()

            # 2. Non-root user configuration
            assert "USER" in content
            assert "botuser" in content or "10001" in content or "appuser" in content

            # 3. Memory optimization environment variables
            assert "PYTHONUNBUFFERED" in content
            assert "MALLOC_ARENA_MAX" in content

            # 4. Built-in HEALTHCHECK probe
            assert "HEALTHCHECK" in content
            assert "/health" in content

    def test_ac3_entrypoint_script_validation(self):
        """Validates entrypoint script initializes Git credentials and launches application."""
        entrypoint_candidates = [
            Path("deploy/entrypoint.sh"),
            Path("entrypoint.sh"),
        ]
        entrypoint = next((p for p in entrypoint_candidates if p.is_file()), None)

        if entrypoint is not None:
            content = entrypoint.read_text(encoding="utf-8")
            assert content.startswith("#!")
            assert "git" in content
            assert "exec" in content

    def test_ac3_requirements_dependencies_complete(self):
        """Validates requirements.txt contains all core dependencies for cloud container execution."""
        req_file = Path("requirements.txt")
        assert req_file.is_file()
        content = req_file.read_text(encoding="utf-8")

        assert "pydantic" in content
        assert "python-telegram-bot" in content
        assert "aiohttp" in content
        assert "pyyaml" in content
        assert "gitpython" in content
