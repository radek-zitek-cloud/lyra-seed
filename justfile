# Lyra Seed — Task Recipes
# Works on both Linux (bash) and Windows (PowerShell)

# Start backend dev server
dev-backend:
    cd backend && uv run uvicorn agent_platform.api.main:app --reload --host 127.0.0.1 --port 8000

# Start frontend dev server
dev-frontend:
    cd frontend && npm run dev

# Start both backend and frontend
dev:
    just dev-backend & just dev-frontend

# Run all backend tests
test:
    cd backend && uv run pytest tests/ -v --tb=short

# Run linter
lint:
    cd backend && uv run ruff check src/ tests/

# Format code
format *args:
    cd backend && uv run ruff format src/ tests/ {{ args }}

# Run all smoke tests
smoke-test:
    cd backend && uv run pytest tests/smoke/ -m smoke -v --tb=short

# Run smoke tests for a specific phase
smoke-test-phase phase:
    cd backend && uv run pytest tests/smoke/ -k "{{ phase }}" -v --tb=short

# Run a single smoke test by ID pattern
smoke-test-id pattern:
    cd backend && uv run pytest tests/smoke/ -k "{{ pattern }}" -v --tb=long

# Database migrations (placeholder)
db-migrate:
    @echo "No migrations to run yet."

# Database reset (placeholder)
db-reset:
    @echo "No database to reset yet."
