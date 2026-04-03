# Lyra — Self-Evolving Multi-Agent Platform

An experimental platform for orchestrating LLM-powered agents with full observability, semantic memory, inter-agent communication, and self-evolving capabilities.

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
- `embeddingModel` — For semantic memory and capability search
- `orchestrationModel` — Cheaper model for orchestration subtasks
- `mcpServers` — MCP tool servers (filesystem, shell, etc.)
- `skillsDir` — Directory for skill files (default `./skills`)
- `dataDir` — Where databases and memory are stored (default `./data`)
- `systemPromptsDir` — Agent prompt templates (default `./prompts`)
- `retry`, `hitl`, `memoryGC`, `context` — Tuning parameters

**Agent config** (`prompts/{name}.json` + `prompts/{name}.md`):
- When you create an agent named "researcher", it loads `prompts/researcher.md` (system prompt) and `prompts/researcher.json` (model, temperature, HITL policy, tool scoping, etc.)
- Falls back to `default.md` / `default.json` if name-specific files don't exist
- See [Configuration Guide](docs/CONFIGURATION_GUIDE.md) for all fields and the resolution chain

### Useful Commands

```bash
just dev              # Start backend + frontend
just dev-backend      # Backend only
just dev-frontend     # Frontend only
just test             # Run all tests
just lint             # Lint check
just format           # Auto-format
just smoke-test       # Run all 152+ smoke tests
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
  Graph View ──────────────── Agent network + orchestration visualization
  Config Editor ───────────── GET/PUT /config/file (+ reload/restart)
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
                     │  ├ Skills            │
                     │  ├ Templates         │
                     │  └ Orchestration     │
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

## Key Features

### Agent Templates
Pre-defined agent roles with specialized prompts, tool access, and configurations:

| Template | Purpose | Tool Access |
|----------|---------|-------------|
| `coder` | Autonomous Python build agent (7-phase TDD workflow) | filesystem, shell |
| `researcher` | Deep research with structured output | none (pure reasoning) |
| `writer` | Polished text production from research | none |
| `editor` | Text review and improvement | none |
| `critic` | Structured critique with PASS/FAIL verdict | none |
| `hitl-worker` | Generic worker with human approval | all |
| `non-hitl-worker` | Generic worker, fully autonomous | all |

Agents discover templates via `list_templates(query="...")` semantic search.

### Skills
Reusable prompt templates loaded from `skills/*.md` files. Agents can:
- **Discover:** `list_skills(query="...")` — semantic search over skill descriptions
- **Test:** `test_skill(template, description, test_args)` — dry-run with LLM evaluation (PASS/FAIL)
- **Create:** `create_skill(name, template, description)` — writes a new skill file with deduplication check
- **Update:** `update_skill(name, template)` — versions the old file, writes new content

### Orchestration
Task decomposition and multi-strategy execution:
- **Sequential** — subtasks run in order
- **Parallel** — independent subtasks run concurrently
- **Pipeline** — each subtask's output feeds into the next
- Per-subtask failure policies: retry, skip, escalate, reassign

### Per-Agent Tool Scoping
Each agent can be configured with `allowed_mcp_servers` and `allowed_tools` to restrict which tools it sees, reducing token cost and enforcing least-privilege access.

### Semantic Discovery
RAG-based capability discovery across three dimensions:
- `list_skills(query="...")` — find relevant skills
- `list_templates(query="...")` — find relevant agent templates
- `recall(query="...")` — find relevant memories

## User Testing / Showcase Guide

Open the UI at `http://localhost:3000`. Use cases are in `docs/agent-drive/`:

| UC | Title | What it showcases |
|----|-------|-------------------|
| [UC-001](docs/agent-drive/UC-001-greeting-memory.md) | Greeting & Memory | Basic chat, auto-extraction, memory recall |
| [UC-002](docs/agent-drive/UC-002-hitl-approval-flow.md) | HITL Approval Flow | Human-in-the-loop approve/deny gates |
| [UC-003](docs/agent-drive/UC-003-tool-system.md) | Tool System | MCP filesystem/shell tools, skills |
| [UC-007](docs/agent-drive/UC-007-orchestration-patterns.md) | Orchestration Patterns | Decompose, sequential/parallel/pipeline execution |
| [UC-008](docs/agent-drive/UC-008-per-agent-tool-scoping.md) | Per-Agent Tool Scoping | MCP server filtering, tool whitelists |
| [UC-011](docs/agent-drive/UC-011-skill-creation-lifecycle.md) | Skill Creation Lifecycle | Search, test, create, dedup, version, update |

Use cases can be run via the UI manually or driven programmatically via the API by Claude Code (see `docs/agent-drive/README.md`).

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
│   │   ├── orchestration/# Task decomposition, strategies, synthesis
│   │   └── tools/        # MCP client, registry, spawner, skills, templates
│   └── tests/smoke/      # 152 smoke tests across 12 phases
├── frontend/             # Next.js + React + TypeScript
│   ├── src/app/          # Pages (agents, memories, graph, config)
│   ├── src/components/   # UI components (detail, messages, graph, HITL)
│   ├── src/hooks/        # SSE event stream, graph data hooks
│   └── tests/smoke/      # Frontend smoke tests
├── prompts/              # Agent prompt templates
│   ├── default.md/json   # Default agent config
│   ├── coder.md/json     # Autonomous Python build agent
│   ├── researcher.md/json# Deep research agent
│   ├── writer.md/json    # Text production agent
│   ├── editor.md/json    # Text editing agent
│   ├── critic.md/json    # Structured critique agent
│   ├── *-worker.md/json  # Worker templates (HITL / non-HITL)
│   └── system/           # Internal prompts (extraction, summarization, evaluation)
├── skills/               # Skill files (.md with YAML frontmatter)
│   ├── summarize.md      # Summarize text into bullet points
│   ├── translate.md      # Translate text to target language
│   └── code-review.md    # Review code for quality and bugs
├── data/                 # Runtime data (gitignored)
│   ├── lyra.db           # SQLite (agents, conversations, events, messages)
│   └── memory/           # ChromaDB persistent storage
├── docs/                 # Project documentation
│   ├── ROADMAP.md        # Full version/phase roadmap
│   ├── REQUIREMENTS.md   # Requirements with delivery status
│   ├── CONFIGURATION_GUIDE.md # All configuration surfaces
│   ├── BACKLOG.md        # Future work items
│   ├── agent-drive/      # API-driven use cases and execution reports
│   └── phases/           # Per-phase plans, tests, status
├── lyra.config.json      # Platform configuration
├── .env                  # Secrets (gitignored)
└── justfile              # Task runner recipes
```

## Current Status

- **V1 Complete:** 8 phases (skeleton, events, runtime, tools, memory, UI, HITL, hardening)
- **V2 Complete:** 7 phases (spawning, messaging, orchestration, tool scoping, graph UI, subtask dispatch, skills)
- **V3P1 Complete:** Skill creation with test/validate, versioning, semantic search, dedup, template discovery
- **152 smoke tests** all passing
- **Next:** V3P2 (MCP Server Creation), BL-008 (Unified RAG Discovery)

## Documentation

- [Roadmap](docs/ROADMAP.md) — Full version/phase plan
- [Requirements](docs/REQUIREMENTS.md) — Feature specifications with delivery status
- [Configuration Guide](docs/CONFIGURATION_GUIDE.md) — All configuration surfaces with examples
- [Agent Templates](prompts/README.md) — Template descriptions and composition patterns
- [Development Methodology](docs/DEVELOPMENT_METHODOLOGY.md) — Phase-driven smoke-test workflow
- [Backlog](docs/BACKLOG.md) — Future work items
