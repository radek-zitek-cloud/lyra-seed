# Lyra — Self-Evolving Multi-Agent Platform

An experimental platform for orchestrating LLM-powered agents with full observability, semantic memory, and inter-agent communication.

**Author:** Radek Zitek / [zitek.cloud](https://zitek.cloud)

## Quick Start

### Prerequisites

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js 18+ with npm
- An [OpenRouter](https://openrouter.ai) API key

### Setup

```bash
# Clone
git clone https://github.com/radek-zitek-cloud/lyra-seed.git
cd lyra-seed

# Configure
cp .env.example .env
cp lyra.config.example.json lyra.config.json
# Edit .env — set your LYRA_OPENROUTER_API_KEY
# Edit lyra.config.json — adjust defaultModel, MCP servers, etc.

# Install backend
cd backend && uv sync && cd ..

# Install frontend
cd frontend && npm install && cd ..

# Start both
just dev
```

Backend runs at `http://localhost:8000`, frontend at `http://localhost:3000`.

### Configuration

**`.env`** — Secrets and server bind only:
```
LYRA_OPENROUTER_API_KEY=sk-or-v1-your-key-here
LYRA_HOST=0.0.0.0
LYRA_PORT=8000
```

**`lyra.config.json`** — Platform configuration:
- `defaultModel` — LLM model for agents (e.g., `openai/gpt-4.1-mini`)
- `embeddingModel` — For semantic memory search
- `mcpServers` — MCP tool servers (filesystem, shell, etc.)
- `dataDir` — Where databases and memory are stored (default `./data`)
- `systemPromptsDir` — Agent prompt templates (default `./prompts`)
- `retry`, `hitl`, `memoryGC`, `context` — Tuning parameters

**Agent config** (`prompts/{name}.json` + `prompts/{name}.md`):
- When you create an agent named "worker", it loads `prompts/worker.md` (system prompt) and `prompts/worker.json` (model, temperature, HITL policy, etc.)
- Falls back to `default.md` / `default.json` if name-specific files don't exist

### Useful Commands

```bash
just dev              # Start backend + frontend
just dev-backend      # Backend only
just dev-frontend     # Frontend only
just test             # Run all tests
just lint             # Lint check
just format           # Auto-format
just smoke-test       # Run all 98+ smoke tests
```

## Architecture

```
Frontend (Next.js)          Backend (FastAPI)
  Agent List ──────────────── GET /agents
  Agent Detail ────────────── GET /agents/{id}
  Conversation ────────────── GET /agents/{id}/conversations
  Event Timeline ──────────── GET /agents/{id}/events (+ SSE stream)
  Messages ────────────────── GET/POST /agents/{id}/messages
  Memory Browser ──────────── GET /memories
  HITL Panel ──────────────── POST /agents/{id}/hitl-respond
                               │
                     ┌─────────┴──────────┐
                     │   Agent Runtime     │
                     │  LLM ↔ Tools Loop   │
                     ├────────────────────┤
                     │  Tool Registry      │
                     │  ├ MCP Servers       │
                     │  ├ Memory Tools      │
                     │  ├ Agent Spawner     │
                     │  └ Prompt Macros     │
                     ├────────────────────┤
                     │  Memory System      │
                     │  ├ ChromaDB Store    │
                     │  ├ Context Manager   │
                     │  ├ Fact Extractor    │
                     │  └ Decay Strategy    │
                     ├────────────────────┤
                     │  Event Bus (SQLite)  │
                     └────────────────────┘
```

## User Testing / Showcase Guide

Open the UI at `http://localhost:3000`. Detailed step-by-step use cases are in `docs/agent-drive/`:

| UC | Title | What it showcases |
|----|-------|-------------------|
| [UC-001](docs/agent-drive/UC-001-greeting-memory.md) | Greeting & Memory | Basic chat, auto-extraction, memory recall |
| [UC-002](docs/agent-drive/UC-002-hitl-approval-flow.md) | HITL Approval Flow | Human-in-the-loop approve/deny gates |
| [UC-003](docs/agent-drive/UC-003-tool-system.md) | Tool System | MCP filesystem/shell tools, prompt macros |
| [UC-004](docs/agent-drive/UC-004-memory-system.md) | Memory System | Remember/recall/forget, cross-agent sharing, decay |
| [UC-005](docs/agent-drive/UC-005-multi-agent-orchestration.md) | Multi-Agent Orchestration | Sub-agent spawning, lifecycle, all 3 orchestration strategies |
| [UC-006](docs/agent-drive/UC-006-inter-agent-communication.md) | Inter-Agent Communication | Message types, auto-wake, stop vs dismiss, reusable workers |
| [UC-007](docs/agent-drive/UC-007-orchestration-patterns.md) | Orchestration Patterns | Decompose, sequential/parallel/pipeline execution |
| [UC-008](docs/agent-drive/UC-008-per-agent-tool-scoping.md) | Per-Agent Tool Scoping | MCP server filtering, tool whitelists |
| [UC-009](docs/agent-drive/UC-009-graph-view.md) | Graph View | Agent network graph, orchestration subtasks, dashboard |

Each UC includes preconditions, step-by-step instructions, expected results, and success criteria. Execution reports (with timestamps and cost data) are in the same directory with `-2026-04-03` suffix.

## Project Structure

```
lyra-seed/
├── backend/              # FastAPI + Python
│   ├── src/agent_platform/
│   │   ├── api/          # Routes, deps, main app factory
│   │   ├── core/         # Runtime, models, config
│   │   ├── db/           # SQLite repositories
│   │   ├── llm/          # OpenRouter provider, embeddings, retry
│   │   ├── memory/       # ChromaDB store, context manager, extractor
│   │   ├── observation/  # Event bus, cost tracker
│   │   └── tools/        # MCP client, registry, spawner, macros
│   └── tests/smoke/      # 98 smoke tests across 10 phases
├── frontend/             # Next.js + React + TypeScript
│   ├── src/app/          # Pages (agents, memories)
│   ├── src/components/   # UI components
│   ├── src/hooks/        # SSE event stream hook
│   └── tests/smoke/      # 6 frontend smoke tests
├── prompts/              # Agent prompt templates
│   ├── default.md/json   # Default agent config
│   ├── worker.md/json    # Worker sub-agent template
│   ├── coder.md/json     # Autonomous Python build agent
│   └── system/           # Internal prompts (extraction, summarization)
├── data/                 # Runtime data (gitignored)
│   ├── lyra.db           # SQLite (agents, conversations, events, messages)
│   └── memory/           # ChromaDB persistent storage
├── docs/                 # Project documentation
│   ├── ROADMAP.md        # Full version/phase roadmap
│   ├── REQUIREMENTS.md   # Requirements with delivery status
│   ├── POST_V1_REPORT.md # V1+V2 completion report
│   └── phases/           # Per-phase plans, tests, status
├── lyra.config.json      # Platform configuration
├── .env                  # Secrets (gitignored)
└── justfile              # Task runner recipes
```

## Current Status

- **V1 Complete:** 8 phases (skeleton, events, runtime, tools, memory, UI, HITL, hardening)
- **V2P1 Complete:** Sub-agent spawning with full tool access
- **V2P2 Complete:** Async spawn, message bus, reusable lifecycle, auto-wake
- **V2 Complete:** 6 phases (spawning, messaging, orchestration, tool scoping, graph UI, subtask dispatch)
- **151 smoke tests** all passing (132 backend + 19 frontend)
- **Next:** V3 (Self-Evolution & Capability Acquisition)

## Documentation

- [Roadmap](docs/ROADMAP.md) — Full version/phase plan
- [Requirements](docs/REQUIREMENTS.md) — Feature specifications with delivery status
- [Development Methodology](docs/DEVELOPMENT_METHODOLOGY.md) — Phase-driven smoke-test workflow
- [Post-V1 Report](docs/POST_V1_REPORT.md) — V1 completion report
- [Post-V2 Report](docs/POST_V2_REPORT.md) — V2 completion report
- [Configuration Guide](docs/CONFIGURATION_GUIDE.md) — All configuration surfaces with examples
