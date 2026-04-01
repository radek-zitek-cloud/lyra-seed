# V1 Phase 0 — Smoke Tests

## Test Environment
- Prerequisites: fresh clone, `uv` and `node`/`npm` installed
- Platform: must pass on both Linux (bash) and Windows (PowerShell)
- All tests run via: `cd backend && uv run pytest tests/smoke/ -k "v1_phase_0" -v --tb=short`

## ST-0.1: Project structure exists
- **Validates:** Monorepo directory layout with all expected packages
- **Method:** Assert existence of key directories and files using `pathlib.Path`
- **Checks:**
  - `backend/src/agent_platform/` directory exists
  - `backend/src/agent_platform/core/` directory exists
  - `backend/src/agent_platform/api/` directory exists
  - `backend/src/agent_platform/llm/` directory exists
  - `backend/src/agent_platform/memory/` directory exists
  - `backend/src/agent_platform/tools/` directory exists
  - `backend/src/agent_platform/db/` directory exists
  - `backend/src/agent_platform/observation/` directory exists
  - `backend/src/agent_platform/orchestration/` directory exists
  - `backend/pyproject.toml` exists and is valid TOML
  - `frontend/package.json` exists and is valid JSON
  - `justfile` exists
  - `.env.example` exists

## ST-0.2: Backend health endpoint responds
- **Validates:** FastAPI app boots and health endpoint works
- **Method:** Use `httpx.AsyncClient` with the app (no subprocess needed)
- **Checks:**
  - `GET /health` returns HTTP 200
  - Response body is `{"status": "ok"}`

## ST-0.3: App factory is callable
- **Validates:** `create_app()` returns a FastAPI instance
- **Method:** Import and call `create_app`, check return type
- **Checks:**
  - `create_app()` returns a `FastAPI` instance
  - `create_app(settings)` accepts a custom settings object

## ST-0.4: Configuration loads from environment
- **Validates:** Pydantic settings model loads correctly
- **Method:** Unit test with env vars set via `monkeypatch`
- **Checks:**
  - Settings model loads with defaults when optional vars are unset
  - `LYRA_OPENROUTER_API_KEY` maps to a `SecretStr` field
  - Setting `LYRA_PORT` env var overrides the default port value
  - Settings with env prefix `LYRA_` are correctly parsed

## ST-0.5: Pytest smoke test harness works
- **Validates:** Smoke test markers and filtering work
- **Method:** Self-referential — this test validates that it was collected with the right markers
- **Checks:**
  - Test is collected when filtering by `-m smoke`
  - Test has the `phase("v1-phase-0")` marker
