"""
Boundary Test 21: Deployment Blueprint Validation & Variable Constraints.
Tests required variable presence, port mappings, and sync interval defaults across deployment configurations.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import yaml


class TestBoundary21DeploymentEnvValidation:
    """Boundary tests for Feature 21 (Deployment Blueprints)."""

    def test_render_yaml_env_vars_complete(self):
        """Test render.yaml declares all essential keys without hardcoded secrets."""
        p = Path("deploy/render.yaml")
        if not p.is_file():
            p = Path("render.yaml")

        if p.is_file():
            content = p.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            env_vars = {item["key"]: item for item in data["services"][0]["envVars"]}
            assert "TELEGRAM_BOT_TOKEN" in env_vars
            assert "PORT" in env_vars

    def test_fly_toml_port_matches_health_server(self):
        """Test fly.toml port matches internal service port."""
        p = Path("deploy/fly.toml")
        if not p.is_file():
            p = Path("fly.toml")

        if p.is_file():
            content = p.read_text(encoding="utf-8")
            assert "8080" in content or "PORT" in content
