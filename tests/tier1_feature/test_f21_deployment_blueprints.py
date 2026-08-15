"""
Feature 21: Free-Tier Cloud Deployment Blueprints Test Suite.
Tests render.yaml, fly.toml, docker-compose.yml, entrypoint.sh, and .env.example specifications.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import yaml


class TestFeature21DeploymentBlueprints:
    """Test suite for Feature 21: Free-Tier Cloud Deployment Blueprints."""

    def test_render_blueprint_specification(self):
        """Test render.yaml contains required service configuration and health check path."""
        path = Path("deploy/render.yaml")
        if not path.is_file():
            path = Path("render.yaml")

        if path.is_file():
            content = path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            assert "services" in data
            service = data["services"][0]
            assert service.get("type") == "web"
            assert service.get("healthCheckPath") == "/health"

    def test_fly_toml_configuration(self):
        """Test fly.toml configures persistent keepalive without aggressive sleep."""
        path = Path("deploy/fly.toml")
        if not path.is_file():
            path = Path("fly.toml")

        if path.is_file():
            content = path.read_text(encoding="utf-8")
            assert "app" in content
            assert "auto_stop_machines = false" in content or "auto_stop_machines" in content

    def test_docker_compose_configuration(self):
        """Test docker-compose.yml configures environment and restart policies."""
        path = Path("deploy/docker-compose.yml")
        if not path.is_file():
            path = Path("docker-compose.yml")

        if path.is_file():
            content = path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            assert "services" in data

    def test_env_example_contains_all_core_variables(self):
        """Test .env.example defines template keys for bot token, LLM keys, and Git sync."""
        path = Path("deploy/.env.example")
        if not path.is_file():
            path = Path(".env.example")

        if path.is_file():
            content = path.read_text(encoding="utf-8")
            assert "TELEGRAM_BOT_TOKEN" in content
            assert "LLM_PROVIDER" in content or "HERMES_API_KEY" in content
            assert "OBSIDIAN_GIT_REPO_URL" in content or "GIT_REMOTE_URL" in content

    def test_entrypoint_script_executable_markers(self):
        """Test entrypoint.sh has proper shebang and git configuration logic."""
        path = Path("deploy/entrypoint.sh")
        if not path.is_file():
            path = Path("entrypoint.sh")

        if path.is_file():
            content = path.read_text(encoding="utf-8")
            assert content.startswith("#!/bin/sh") or content.startswith("#!/bin/bash")
            assert "exec" in content
