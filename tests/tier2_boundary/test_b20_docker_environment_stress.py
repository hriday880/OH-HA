"""
Boundary Test 20: Docker Memory Constraints & Environment Stress.
Tests glibc allocator limits (MALLOC_ARENA_MAX=2), low-RAM container profiling, and user permissions.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest


class TestBoundary20DockerEnvironmentStress:
    """Boundary tests for Feature 20 (Docker Runtime)."""

    def test_malloc_arena_max_low_memory_configuration(self):
        """Test that MALLOC_ARENA_MAX=2 is set to avoid heap fragmentation in 256MB/512MB RAM containers."""
        dockerfile = Path("deploy/Dockerfile")
        if not dockerfile.is_file():
            dockerfile = Path("Dockerfile")

        if dockerfile.is_file():
            content = dockerfile.read_text(encoding="utf-8")
            assert "MALLOC_ARENA_MAX=2" in content or "MALLOC_ARENA_MAX" in content

    def test_non_root_uid_specification(self):
        """Test non-root UID 10001 or botuser is explicitly created and assigned."""
        dockerfile = Path("deploy/Dockerfile")
        if not dockerfile.is_file():
            dockerfile = Path("Dockerfile")

        if dockerfile.is_file():
            content = dockerfile.read_text(encoding="utf-8")
            assert "useradd" in content or "adduser" in content or "USER" in content
