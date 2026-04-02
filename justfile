# Lyra Seed — Task Recipes
# Works on both Linux (bash) and Windows (PowerShell)

set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# Start backend dev server
dev-backend:
    uv run --directory backend uvicorn agent_platform.api.main:app --reload --host 127.0.0.1 --port 8000

# Start frontend dev server
dev-frontend:
    npm run --prefix frontend dev

# Start both backend and frontend
dev:
    just dev-backend & just dev-frontend

# Run all backend tests
test:
    uv run --directory backend pytest tests/ -v --tb=short

# Run linter
lint:
    uv run --directory backend ruff check src/ tests/

# Format code
format *args:
    uv run --directory backend ruff format src/ tests/ {{ args }}

# Run all smoke tests
smoke-test:
    uv run --directory backend pytest tests/smoke/ -m smoke -v --tb=short

# Run smoke tests for a specific phase
smoke-test-phase phase:
    uv run --directory backend pytest tests/smoke/ -k "{{ phase }}" -v --tb=short

# Run a single smoke test by ID pattern
smoke-test-id pattern:
    uv run --directory backend pytest tests/smoke/ -k "{{ pattern }}" -v --tb=long

# Database migrations (placeholder)
db-migrate:
    @echo "No migrations to run yet."

# Database reset (placeholder)
db-reset:
    @echo "No database to reset yet."
