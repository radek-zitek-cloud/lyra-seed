# V1 Phase 0 — Plan

## Phase Reference
- **Version:** V1
- **Phase:** 0
- **Title:** Project Skeleton & Tooling
- **Roadmap Section:** §4, V1 Phase 0

## Prerequisites
- None (this is the first phase)

## Deliverables Checklist
- [ ] Monorepo directory structure with all package directories
- [ ] Backend: `pyproject.toml` with uv, FastAPI, Pydantic, dev dependencies
- [ ] Backend: App factory (`create_app`) with health-check endpoint
- [ ] Backend: Pydantic settings model (env-based configuration)
- [ ] Backend: Pytest configuration with smoke/phase markers and async support
- [ ] Frontend: Next.js project with `package.json` and TypeScript
- [ ] `justfile` with cross-platform recipes (dev, test, lint, format, smoke-test)
- [ ] `.env.example` with documented configuration variables
- [ ] `.gitignore` for Python, Node.js, and project-specific files

## Implementation Steps

1. **Create backend package structure**
   - Initialize `backend/pyproject.toml` with uv
   - Create `backend/src/agent_platform/` package with `__init__.py`
   - Create sub-packages: `core/`, `llm/`, `memory/`, `tools/`, `orchestration/`, `observation/`, `db/`, `api/`
   - Each sub-package gets an `__init__.py`

2. **Add backend dependencies**
   - Runtime: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `httpx`, `aiosqlite`
   - Dev: `pytest`, `pytest-asyncio`, `httpx` (for test client), `ruff`, `mypy`
   - Configure in `pyproject.toml` with dependency groups

3. **Create Pydantic settings model**
   - `backend/src/agent_platform/core/config.py`
   - Fields: `openrouter_api_key` (SecretStr), `default_model`, `db_path`, `host`, `port`
   - Env prefix: `LYRA_`
   - Sensible defaults matching `.env.example`

4. **Create FastAPI app factory**
   - `backend/src/agent_platform/api/main.py`
   - `create_app(settings=None) -> FastAPI` function
   - Health endpoint: `GET /health` returning `{"status": "ok"}`
   - Module-level `app = create_app()` for uvicorn

5. **Configure pytest**
   - `backend/tests/conftest.py` with phase marker support
   - `backend/tests/smoke/conftest.py` for smoke test fixtures
   - Pytest config in `pyproject.toml`: asyncio_mode, markers, testpaths

6. **Create frontend project**
   - Initialize Next.js in `frontend/` with TypeScript
   - Minimal `src/app/page.tsx` with placeholder content
   - Add test scripts to `package.json`

7. **Create justfile**
   - `dev-backend`: start uvicorn
   - `dev-frontend`: start Next.js dev server
   - `dev`: start both (background backend + foreground frontend)
   - `test`: run pytest
   - `lint`: run ruff check
   - `format`: run ruff format
   - `smoke-test`: run smoke tests
   - `smoke-test-phase`: run smoke tests for a specific phase

8. **Create `.env.example` and `.gitignore`**
   - `.env.example` with all config vars (no real secrets)
   - `.gitignore` for Python, Node.js, SQLite, IDE files

## Dependencies & Libraries

### Backend (Python)
| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | >=0.115 | Web framework |
| uvicorn[standard] | >=0.34 | ASGI server |
| pydantic | >=2.0 | Data validation |
| pydantic-settings | >=2.0 | Environment-based configuration |
| httpx | >=0.28 | Async HTTP client (runtime + test) |
| aiosqlite | >=0.20 | Async SQLite driver |
| pytest | >=8.0 | Test framework (dev) |
| pytest-asyncio | >=0.25 | Async test support (dev) |
| ruff | >=0.11 | Linter and formatter (dev) |
| mypy | >=1.14 | Type checker (dev) |

### Frontend (Node.js)
| Package | Version | Purpose |
|---------|---------|---------|
| next | latest | React framework |
| react | latest | UI library |
| typescript | latest | Type safety |

## File Manifest

- `backend/pyproject.toml` — Python project config, dependencies, pytest settings
- `backend/src/agent_platform/__init__.py` — Package root
- `backend/src/agent_platform/core/__init__.py` — Core sub-package
- `backend/src/agent_platform/core/config.py` — Pydantic settings model
- `backend/src/agent_platform/api/__init__.py` — API sub-package
- `backend/src/agent_platform/api/main.py` — FastAPI app factory + health endpoint
- `backend/src/agent_platform/llm/__init__.py` — LLM sub-package (empty)
- `backend/src/agent_platform/memory/__init__.py` — Memory sub-package (empty)
- `backend/src/agent_platform/tools/__init__.py` — Tools sub-package (empty)
- `backend/src/agent_platform/orchestration/__init__.py` — Orchestration sub-package (empty)
- `backend/src/agent_platform/observation/__init__.py` — Observation sub-package (empty)
- `backend/src/agent_platform/db/__init__.py` — DB sub-package (empty)
- `backend/tests/__init__.py` — Test package
- `backend/tests/conftest.py` — Root conftest with marker registration
- `backend/tests/smoke/__init__.py` — Smoke test package
- `backend/tests/smoke/conftest.py` — Smoke test fixtures
- `backend/tests/smoke/test_v1_phase_0.py` — Phase 0 smoke tests
- `frontend/package.json` — Node.js project config
- `frontend/tsconfig.json` — TypeScript config
- `frontend/src/app/layout.tsx` — Next.js root layout
- `frontend/src/app/page.tsx` — Placeholder home page
- `justfile` — Cross-platform task recipes
- `.env.example` — Example environment configuration
- `.gitignore` — Git ignore rules

## Risks & Decisions

- **uv vs pip:** Using uv for dependency management. If uv is not installed, recipes will fail — document in README.
- **Next.js initialization:** Will use manual file creation rather than `create-next-app` to keep it minimal and avoid interactive prompts.
- **Cross-platform justfile:** The `just` tool supports both bash and PowerShell. Recipes must avoid shell-specific syntax where possible.
- **Port defaults:** Backend on 8000, frontend on 3000 — matches common conventions.
