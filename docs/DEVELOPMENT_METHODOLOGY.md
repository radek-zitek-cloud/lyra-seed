# Development Methodology — Phase-Driven Smoke-Test Loop

> **Purpose:** Define the exact workflow Claude Code follows when implementing any phase of the roadmap.
> **Rule:** No phase is considered complete until all its smoke tests pass automatically.

---

## 1. Workflow Overview

```
┌─────────────────────────────────────────────────────────┐
│                   PHASE EXECUTION LOOP                   │
│                                                          │
│  1. READ phase from ROADMAP.md                          │
│  2. GENERATE plan + smoke tests → store in docs/phases/ │
│  3. IMPLEMENT code according to plan                    │
│  4. RUN smoke tests (just smoke-test-phase V1P0)        │
│  5. ALL PASS? ──yes──▶ Mark phase DONE, commit          │
│       │                                                  │
│       no                                                 │
│       │                                                  │
│  6. ANALYZE failures                                    │
│  7. FIX code ──────▶ Go to step 4                       │
└─────────────────────────────────────────────────────────┘
```

Claude Code **never** declares a phase complete based on intent or visual inspection. The smoke test suite is the **sole authority** on phase completion.

---

## 2. Project Structure for Plans & Tests

```
/
├── docs/
│   └── phases/
│       ├── v1-phase-0/
│       │   ├── PLAN.md              # Implementation plan
│       │   ├── SMOKE_TESTS.md       # Human-readable smoke test specs
│       │   └── STATUS.md            # Current status, blockers, log
│       ├── v1-phase-1/
│       │   ├── PLAN.md
│       │   ├── SMOKE_TESTS.md
│       │   └── STATUS.md
│       └── ...
├── backend/
│   └── tests/
│       └── smoke/
│           ├── conftest.py          # Shared smoke test fixtures
│           ├── test_v1_phase_0.py   # Smoke tests for V1 Phase 0
│           ├── test_v1_phase_1.py   # Smoke tests for V1 Phase 1
│           └── ...
├── frontend/
│   └── tests/
│       └── smoke/
│           ├── smoke.v1-phase-5.spec.ts  # Frontend smoke tests
│           └── ...
└── justfile                         # Includes smoke test recipes
```

---

## 3. Phase Plan Document (PLAN.md)

Every phase plan follows this template:

```markdown
# V1 Phase 0 — Plan

## Phase Reference
- **Version:** V1
- **Phase:** 0
- **Title:** Project Skeleton & Tooling
- **Roadmap Section:** §4, V1 Phase 0

## Prerequisites
- List of phases that must be complete before this one
- External dependencies (tools to install, accounts to create)

## Deliverables Checklist
- [ ] Deliverable 1 (from roadmap)
- [ ] Deliverable 2
- [ ] ...

## Implementation Steps
Ordered list of concrete implementation steps. Each step should be
small enough that Claude Code can execute it in a single action.

1. **Step title**
   - What to create/modify
   - Specific files involved
   - Commands to run
   - Acceptance: how to know this step is done

2. **Step title**
   - ...

## Dependencies & Libraries
- Exact package names and version constraints
- Why each dependency is needed

## File Manifest
List of all files this phase will create or modify:
- `path/to/file.py` — purpose
- `path/to/other.py` — purpose

## Risks & Decisions
- Known unknowns or choices to be made during implementation
- Fallback approaches if primary approach fails
```

---

## 4. Smoke Test Specification (SMOKE_TESTS.md)

The human-readable specification that drives the automated tests. Every smoke test maps to a deliverable in the plan.

```markdown
# V1 Phase 0 — Smoke Tests

## Test Environment
- Prerequisites: fresh clone, no prior state
- Platform: must pass on both Linux (bash) and Windows (PowerShell)

## ST-0.1: Project structure exists
- **Validates:** Monorepo directory layout
- **Method:** Assert existence of key directories and files
- **Checks:**
  - `backend/src/agent_platform/` directory exists
  - `backend/pyproject.toml` exists and is valid TOML
  - `frontend/package.json` exists and is valid JSON
  - `justfile` exists
  - `.env.example` exists

## ST-0.2: Backend starts and serves health check
- **Validates:** FastAPI app boots, health endpoint responds
- **Method:** Start backend server, HTTP GET /health
- **Checks:**
  - Server starts without error on configured port
  - `GET /health` returns 200 with `{"status": "ok"}`
  - Server shuts down cleanly

## ST-0.3: Frontend starts
- **Validates:** Next.js dev server boots
- **Method:** Start frontend, check it serves a page
- **Checks:**
  - Dev server starts without error
  - `GET /` returns 200 (or 302 to a valid page)

## ST-0.4: Justfile recipes execute
- **Validates:** Core justfile recipes work
- **Method:** Run each recipe, assert exit code 0
- **Checks:**
  - `just lint` exits 0 (no lint errors in skeleton)
  - `just format --check` exits 0 (code already formatted)
  - `just test` exits 0 (placeholder test passes)

## ST-0.5: Configuration loads from environment
- **Validates:** Pydantic settings model
- **Method:** Unit test with env vars set
- **Checks:**
  - Settings model loads with defaults from `.env.example`
  - Required fields without defaults raise validation error
  - Sensitive fields (API keys) are `SecretStr` type
```

### Smoke Test Naming Convention

Each smoke test has an ID: `ST-{version}{phase}.{sequence}`

- `ST-0.1` → V1 Phase 0, test 1
- `ST-1.3` → V1 Phase 1, test 3
- `ST-V2-1.2` → V2 Phase 1, test 2

---

## 5. Automated Smoke Test Harness

### 5.1 Backend Smoke Tests (Python / pytest)

All backend smoke tests live in `backend/tests/smoke/` and follow these conventions:

```python
"""
Smoke tests for V1 Phase 0 — Project Skeleton & Tooling.

Each test function maps to a smoke test ID from SMOKE_TESTS.md.
Test functions are named: test_st_<phase>_<sequence>_<short_description>
"""
import pytest

# Markers for filtering
pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v1-phase-0"),
]


class TestV1Phase0:
    """ST-0.x: Project Skeleton & Tooling smoke tests."""

    def test_st_0_1_project_structure(self):
        """ST-0.1: Project structure exists."""
        ...

    @pytest.mark.asyncio
    async def test_st_0_2_backend_health(self):
        """ST-0.2: Backend starts and serves health check."""
        ...
```

**Key conventions:**

- Every test docstring starts with its smoke test ID (e.g., `ST-0.1`)
- Tests are marked with `@pytest.mark.smoke` and `@pytest.mark.phase("v1-phase-X")`
- Tests are **independent** — no ordering dependency between them
- Tests clean up after themselves (temp files, spawned processes, DB state)
- Tests must complete within a reasonable timeout (30s default, configurable)
- No external service dependencies in smoke tests (LLM calls are mocked)

### 5.2 Frontend Smoke Tests (TypeScript / Vitest or Playwright)

Frontend smoke tests live in `frontend/tests/smoke/` and follow analogous conventions:

```typescript
// smoke.v1-phase-5.spec.ts
describe('V1 Phase 5 — Observation UI', () => {
  test('ST-5.1: Agent list page renders', async () => {
    // ...
  });

  test('ST-5.2: Event timeline displays events', async () => {
    // ...
  });
});
```

### 5.3 Process-Level Smoke Tests

Some smoke tests need to verify that servers start, ports bind, and processes communicate. These use a harness pattern:

```python
@pytest.fixture
async def backend_server():
    """Start the backend server as a subprocess, yield when ready, kill on cleanup."""
    proc = await asyncio.create_subprocess_exec(
        "uvicorn", "agent_platform.api.main:app",
        "--host", "127.0.0.1", "--port", "0",  # OS-assigned port
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    port = await _wait_for_server_ready(proc)  # Parse port from stdout
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    await proc.wait()
```

### 5.4 Mock & Fixture Strategy

| Dependency         | Smoke Test Approach                                      |
|--------------------|----------------------------------------------------------|
| LLM Provider       | Mock — returns canned responses from fixture files       |
| OpenRouter API     | Mock — never called in smoke tests                       |
| SQLite DB          | Real — uses temp file, deleted after test                |
| MCP Servers        | Mock — stub MCP server in-process                        |
| Embedding API      | Mock — returns deterministic fake vectors                |
| File system        | Real — uses `tmp_path` pytest fixture                    |
| Network (HTTP)     | Real loopback only — `httpx.AsyncClient` with `app`     |
| WebSocket          | Real loopback — test client connects to test server      |

---

## 6. Justfile Integration

```justfile
# ──────────────────────────────────────
# Smoke Test Recipes
# ──────────────────────────────────────

# Run all smoke tests
smoke-test:
    cd backend && uv run pytest tests/smoke/ -m smoke -v --tb=short

# Run smoke tests for a specific phase
smoke-test-phase phase:
    cd backend && uv run pytest tests/smoke/ -m "phase('{{phase}}')" -v --tb=short

# Run a single smoke test by ID pattern
smoke-test-id pattern:
    cd backend && uv run pytest tests/smoke/ -k "{{pattern}}" -v --tb=long

# Run frontend smoke tests
smoke-test-frontend:
    cd frontend && npm run test:smoke

# Run ALL smoke tests (backend + frontend)
smoke-test-all: smoke-test smoke-test-frontend

# ──────────────────────────────────────
# Phase Management
# ──────────────────────────────────────

# Show status of all phases
phase-status:
    @echo "Phase Status:"
    @for dir in docs/phases/*/; do \
        phase=$(basename "$dir"); \
        if [ -f "$dir/STATUS.md" ]; then \
            status=$(head -1 "$dir/STATUS.md" | sed 's/# //'); \
            echo "  $phase: $status"; \
        else \
            echo "  $phase: NOT STARTED"; \
        fi \
    done
```

---

## 7. Status Tracking (STATUS.md)

Each phase has a `STATUS.md` updated by Claude Code during execution:

```markdown
# V1 Phase 0 — IN PROGRESS

## Current State
- Started: 2026-04-01T14:00:00Z
- Last updated: 2026-04-01T15:30:00Z

## Smoke Test Results
| ID     | Description                | Status | Notes          |
|--------|----------------------------|--------|----------------|
| ST-0.1 | Project structure exists   | PASS   |                |
| ST-0.2 | Backend health check       | PASS   |                |
| ST-0.3 | Frontend starts            | FAIL   | Port conflict   |
| ST-0.4 | Justfile recipes           | SKIP   | Blocked by 0.3 |
| ST-0.5 | Config loads               | PASS   |                |

## Iteration Log
### Iteration 1 (14:00–14:45)
- Implemented: project structure, pyproject.toml, basic FastAPI app
- Tests run: 3/5 passed
- Failures: ST-0.3 (Next.js config issue), ST-0.4 (blocked)

### Iteration 2 (14:45–15:30)
- Fixed: Next.js config, added proper dev script
- Tests run: 5/5 passed
- ✅ Phase complete

## Blockers Encountered
- None

## Decisions Made
- Chose `src/` layout over flat layout for backend (pytest discovery works better)
- Used port 3000 for frontend, 8000 for backend as defaults
```

---

## 8. Claude Code Execution Protocol

When Claude Code starts work on a phase, it follows this exact sequence:

### Step 1: Preparation
1. Read `ROADMAP.md` — extract the target phase's deliverables and exit criteria
2. Read prior phase's `STATUS.md` — confirm prerequisites are met
3. Check if `docs/phases/{phase}/PLAN.md` already exists
   - If yes: review and confirm it's still valid
   - If no: generate it

### Step 2: Plan & Smoke Test Generation
1. Create `docs/phases/{phase}/PLAN.md` following the template (§3)
2. Create `docs/phases/{phase}/SMOKE_TESTS.md` following the template (§4)
3. **Present both to the human for review before proceeding**
4. Create the automated smoke test file(s) in `backend/tests/smoke/` and/or `frontend/tests/smoke/`

### Step 3: Implementation Loop
```
while not all_smoke_tests_pass:
    implement_next_deliverable()
    run_smoke_tests()
    if failures:
        analyze_failure_output()
        fix_code()
    update_status_md()
```

### Step 4: Completion
1. Run full smoke test suite one final time
2. Update `STATUS.md` with final results and mark `COMPLETE`
3. Run `just lint` and `just format` — fix any issues
4. Run prior phases' smoke tests to confirm no regressions
5. Present summary to human

### Regression Rule
Before marking any phase complete, Claude Code must also run smoke tests for **all previously completed phases**. A phase cannot introduce regressions.

---

## 9. Test Harness Requirements

For the smoke-test-driven loop to work, the codebase must satisfy these structural requirements from Phase 0 onward:

### 9.1 Backend

- **Testable app factory:** The FastAPI app must be creatable via a function (not a module-level singleton) so tests can instantiate it with test config:
  ```python
  # agent_platform/api/main.py
  def create_app(settings: Settings | None = None) -> FastAPI:
      ...
  
  # For uvicorn:
  app = create_app()
  ```

- **Dependency injection via FastAPI `Depends`:** All services (DB, LLM provider, event bus) injected so tests can override them with mocks.

- **Async test support:** `pytest-asyncio` configured from day one.

- **Pytest configuration in `pyproject.toml`:**
  ```toml
  [tool.pytest.ini_options]
  asyncio_mode = "auto"
  markers = [
      "smoke: Smoke tests for phase validation",
      "phase(name): Filter tests by phase identifier",
  ]
  testpaths = ["tests"]
  ```

- **Custom pytest marker for phase filtering:**
  ```python
  # tests/conftest.py or plugin
  def pytest_configure(config):
      config.addinivalue_line("markers", "phase(name): phase identifier")
  
  # Usage in collection
  def pytest_collection_modifyitems(config, items):
      phase_filter = config.getoption("-m", default="")
      # Custom logic to filter by phase('v1-phase-0') syntax
  ```

### 9.2 Frontend

- **Test script in `package.json`:**
  ```json
  {
    "scripts": {
      "test": "vitest run",
      "test:smoke": "vitest run tests/smoke/",
      "test:watch": "vitest"
    }
  }
  ```

- **Vitest configured** with project paths and any required transforms.

### 9.3 Cross-Platform Considerations

- Smoke tests must not rely on Unix-specific paths or commands
- File path assertions use `pathlib.Path` (Python) or `path.join` (TS)
- Process spawning uses `asyncio.create_subprocess_exec` (not `os.system`)
- Temporary directories via `tmp_path` fixture (Python) or `os.tmpdir()` (TS)
- All justfile recipes that invoke smoke tests must work in both bash and PowerShell

---

## 10. Naming & Convention Summary

| Item                     | Convention                                              | Example                          |
|--------------------------|---------------------------------------------------------|----------------------------------|
| Phase directory          | `v{version}-phase-{number}`                            | `v1-phase-0`                     |
| Smoke test ID            | `ST-{phase}.{sequence}`                                | `ST-0.1`, `ST-1.3`              |
| Python test file         | `test_v{version}_phase_{number}.py`                    | `test_v1_phase_0.py`            |
| Python test function     | `test_st_{phase}_{seq}_{description}`                  | `test_st_0_1_project_structure`  |
| Python test class        | `TestV{version}Phase{number}`                          | `TestV1Phase0`                   |
| Pytest marker            | `@pytest.mark.phase("v1-phase-0")`                     |                                  |
| Frontend test file       | `smoke.v{version}-phase-{number}.spec.ts`              | `smoke.v1-phase-5.spec.ts`      |
| Justfile recipe          | `smoke-test-phase v1-phase-0`                           |                                  |
| Status values            | `NOT STARTED`, `IN PROGRESS`, `COMPLETE`, `BLOCKED`    |                                  |

---

## 11. Agent Configuration Resolution Pattern

All configurable agent parameters follow a **four-level resolution chain**. Most specific wins:

```
prompts/{agent-name}.json   →  per-agent override
prompts/default.json        →  default for all agents
lyra.config.json            →  platform-wide config
hardcoded defaults          →  fallback in Pydantic models
```

### Resolution flow

1. Agent is created via `POST /agents` with a name
2. `resolve_agent_config(name)` checks `prompts/{name}.json`, falls back to `prompts/default.json`
3. File config fields override `AgentConfig` defaults
4. For fields not set by file config, `PlatformConfig` values from `lyra.config.json` are applied
5. Any remaining fields use hardcoded Pydantic defaults

### Configuration sections

| Section | Platform (`lyra.config.json`) | Agent file (`{name}.json`) | `AgentConfig` field |
|---------|-------------------------------|---------------------------|---------------------|
| **Retry** | `retry: {max_retries, base_delay, max_delay, timeout}` | `retry: {...}` | `retry: AgentRetryConfig` |
| **HITL** | `hitl: {timeout_seconds}` | `hitl: {timeout_seconds}` | `hitl_timeout_seconds` |
| **Memory GC** | `memoryGC: {prune_threshold, max_entries}` | `memoryGC: {...}` | `prune_threshold`, `prune_max_entries` |
| **Context** | `context: {max_tokens, memory_top_k}` | `context: {...}` | `max_context_tokens`, `memory_top_k` |
| **Model** | `defaultModel` | `model` | `model` |
| **Temperature** | — | `temperature` | `temperature` |
| **Iterations** | — | `max_iterations` | `max_iterations` |
| **HITL Policy** | — | `hitl_policy` | `hitl_policy` |

### Adding a new configurable parameter

1. Add a config model to `platform_config.py` (e.g. `class NewConfig(BaseModel)`)
2. Add it to `PlatformConfig` with a default
3. Add it to `AgentFileConfig` as optional (`NewConfig | None = None`)
4. Add the resolved field to `AgentConfig` in `models.py`
5. Apply it in `routes.py`: file override → platform fallback → hardcoded default
6. Use it from `agent.config.field_name` in the runtime
7. Add to `lyra.config.json`, `lyra.config.example.json`, and `prompts/default.json`