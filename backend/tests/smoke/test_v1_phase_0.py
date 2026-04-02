"""
Smoke tests for V1 Phase 0 — Project Skeleton & Tooling.

Each test function maps to a smoke test ID from SMOKE_TESTS.md.
Test functions are named: test_st_<phase>_<sequence>_<short_description>
"""

import json
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v1-phase-0"),
]


class TestV1Phase0:
    """ST-0.x: Project Skeleton & Tooling smoke tests."""

    def test_st_0_1_project_structure(self, project_root: Path):
        """ST-0.1: Project structure exists."""
        # Backend package directories
        agent_pkg = project_root / "backend" / "src" / "agent_platform"
        assert agent_pkg.is_dir(), "backend/src/agent_platform/ must exist"

        expected = [
            "core",
            "api",
            "llm",
            "memory",
            "tools",
            "db",
            "observation",
            "orchestration",
        ]
        for subpkg in expected:
            assert (agent_pkg / subpkg).is_dir(), f"agent_platform/{subpkg}/ must exist"

        # Key files
        pyproject = project_root / "backend" / "pyproject.toml"
        assert pyproject.is_file(), "backend/pyproject.toml must exist"

        # Validate TOML is parseable
        import tomllib

        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        assert "project" in data, "pyproject.toml must have [project] section"

        # Frontend
        pkg_json = project_root / "frontend" / "package.json"
        assert pkg_json.is_file(), "frontend/package.json must exist"
        with open(pkg_json) as f:
            data = json.load(f)
        assert "name" in data, "package.json must have a name field"

        # Root files
        assert (project_root / "justfile").is_file(), "justfile must exist"
        assert (project_root / ".env.example").is_file(), ".env.example must exist"

    @pytest.mark.asyncio
    async def test_st_0_2_backend_health(self):
        """ST-0.2: Backend starts and serves health check."""
        import httpx

        from agent_platform.api.main import create_app

        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_st_0_3_app_factory(self):
        """ST-0.3: App factory is callable and returns FastAPI."""
        from fastapi import FastAPI

        from agent_platform.api.main import create_app

        # Without settings
        app = create_app()
        assert isinstance(app, FastAPI)

        # With custom settings
        from agent_platform.core.config import Settings

        settings = Settings(
            openrouter_api_key="test-key",  # type: ignore[arg-type]
        )
        app_with_settings = create_app(settings=settings)
        assert isinstance(app_with_settings, FastAPI)

    def test_st_0_4_config_loads(self, monkeypatch: pytest.MonkeyPatch):
        """ST-0.4: Configuration loads from environment."""
        from pydantic import SecretStr

        from agent_platform.core.config import Settings

        # Set required env vars
        monkeypatch.setenv("LYRA_OPENROUTER_API_KEY", "sk-test-key-12345")
        monkeypatch.setenv("LYRA_PORT", "9999")

        settings = Settings()  # type: ignore[call-arg]

        # API key is SecretStr
        assert isinstance(settings.openrouter_api_key, SecretStr)
        assert settings.openrouter_api_key.get_secret_value() == "sk-test-key-12345"

        # Port override works
        assert settings.port == 9999

        # Defaults exist for optional fields
        assert settings.host is not None

    def test_st_0_5_smoke_harness(self, request: pytest.FixtureRequest):
        """ST-0.5: Pytest smoke test harness works."""
        # Verify this test has the smoke marker
        markers = [m.name for m in request.node.iter_markers()]
        assert "smoke" in markers, "Test must have @pytest.mark.smoke"

        # Verify this test has the phase marker
        phase_markers = [m for m in request.node.iter_markers(name="phase")]
        assert len(phase_markers) > 0, "Test must have @pytest.mark.phase"
        assert phase_markers[0].args[0] == "v1-phase-0"
