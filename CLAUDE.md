# CLAUDE.md — Project Instructions for Claude Code

## Project

Self-evolving multi-agent platform. Experimental hobby project by Radek Zítek (zitek.cloud).

## Key Documents

Before doing any implementation work, read these files from the project root:

- `REQUIREMENTS.md` — High-level requirements and use cases
- `ROADMAP.md` — Detailed version/phase roadmap with deliverables and exit criteria
- `METHODOLOGY.md` — Development workflow (phase-driven smoke-test loop)

## Development Methodology

This project uses a **phase-driven smoke-test loop**. The methodology is fully documented in `METHODOLOGY.md`. The key rule: **no phase is complete until all its smoke tests pass automatically.**

Phase plans and status are stored in `docs/phases/{version}-phase-{number}/`.

## Tech Stack

- **Backend:** Python, FastAPI, Pydantic, SQLite (uv for dependency management)
- **Frontend:** TypeScript, React, Next.js
- **Task runner:** justfile (must work on both Linux bash and Windows PowerShell)
- **LLM:** OpenRouter (behind abstract provider interface)
- **Embeddings:** openai/text-embedding-3-large via OpenRouter

## Conventions

- All code must work cross-platform (Linux + Windows)
- FastAPI uses app factory pattern: `create_app(settings)`
- All services injected via FastAPI `Depends` (testable, mockable)
- Pydantic models for all data contracts
- Async-first throughout the backend
- Smoke tests use pytest markers: `@pytest.mark.smoke`, `@pytest.mark.phase("v1-phase-0")`
- LLM and external API calls are always mocked in smoke tests
- Every significant action emits an event via the EventBus

## Useful Commands

```bash
just dev              # Start backend + frontend
just dev-backend      # Start backend only
just dev-frontend     # Start frontend only
just test             # Run all tests
just lint             # Run linter
just format           # Format code
just smoke-test       # Run all smoke tests
just smoke-test-phase v1-phase-0  # Run smoke tests for a specific phase
```