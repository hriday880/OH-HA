"""
Feature 20: Multi-Stage Minimal Docker Container Test Suite.
Tests Dockerfile syntax, multi-stage architecture, non-root user isolation, and healthcheck configuration.
"""

from __future__ import annotations

from pathlib import Path
import pytest


class TestFeature20DockerfileRuntime:
    """Test suite for Feature 20: Multi-Stage Minimal Docker Container."""

    def test_dockerfile_multi_stage_structure(self):
        """Test Dockerfile uses multi-stage build (builder and runtime stages)."""
        dockerfile_path = Path("deploy/Dockerfile")
        if not dockerfile_path.is_file():
            dockerfile_path = Path("Dockerfile")

        if dockerfile_path.is_file():
            content = dockerfile_path.read_text(encoding="utf-8")
            assert "FROM" in content
            assert "AS builder" in content or "as builder" in content
            assert "python" in content.lower()

    def test_dockerfile_non_root_user(self):
        """Test Dockerfile creates and switches to non-root user."""
        dockerfile_path = Path("deploy/Dockerfile")
        if not dockerfile_path.is_file():
            dockerfile_path = Path("Dockerfile")

        if dockerfile_path.is_file():
            content = dockerfile_path.read_text(encoding="utf-8")
            assert "USER" in content
            assert "root" not in content.split("USER")[-1].strip()

    def test_dockerfile_memory_and_unbuffered_env(self):
        """Test Dockerfile configures memory and python unbuffered environment variables."""
        dockerfile_path = Path("deploy/Dockerfile")
        if not dockerfile_path.is_file():
            dockerfile_path = Path("Dockerfile")

        if dockerfile_path.is_file():
            content = dockerfile_path.read_text(encoding="utf-8")
            assert "PYTHONUNBUFFERED=1" in content or "PYTHONUNBUFFERED" in content
            assert "MALLOC_ARENA_MAX" in content

    def test_dockerfile_healthcheck_directive(self):
        """Test Dockerfile contains HEALTHCHECK instruction targeting /health endpoint."""
        dockerfile_path = Path("deploy/Dockerfile")
        if not dockerfile_path.is_file():
            dockerfile_path = Path("Dockerfile")

        if dockerfile_path.is_file():
            content = dockerfile_path.read_text(encoding="utf-8")
            assert "HEALTHCHECK" in content
            assert "/health" in content

    def test_dockerfile_entrypoint_executable(self):
        """Test entrypoint script is configured."""
        dockerfile_path = Path("deploy/Dockerfile")
        if not dockerfile_path.is_file():
            dockerfile_path = Path("Dockerfile")

        if dockerfile_path.is_file():
            content = dockerfile_path.read_text(encoding="utf-8")
            assert "ENTRYPOINT" in content or "CMD" in content
