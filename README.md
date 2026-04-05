# Lyra — Self-Evolving Multi-Agent Platform

An experimental platform for orchestrating LLM-powered agents with full observability, semantic memory, inter-agent communication, knowledge base, and self-evolving capabilities.

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
LYRA_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

**`lyra.config.json`** — Platform configuration:
- `defaultModel` — LLM model for agents (e.g., `openai/gpt-4.1-mini`)
- `embeddingModel` — For semantic memory, knowledge, and capability search
- `orchestrationModel` — Cheaper model for orchestration subtasks
- `mcpServers` — MCP tool servers (filesystem, shell, etc.)
- `knowledgeDir` — Directory for knowledge base documents (default `./knowledge`)
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
just smoke-test       # Run all smoke tests
just smoke-test-phase v4-phase-3   # Run smoke tests for a specific phase
just smoke-test-id pattern         # Run a single smoke test by ID pattern
```

## Architecture

```
Frontend (Next.js)          Backend (FastAPI)
  Agent List ──────────────── GET /agents
  Agent Detail ────────────── GET /agents/{id}  (config, system prompt)
  Conversation ────────────── GET /agents/{id}/conversations
  Event Timeline ──────────── GET /agents/{id}/events (+ SSE stream)
  Global Events ───────────── GET /events (+ SSE /events/stream)
  Messages ────────────────── GET/POST /agents/{id}/messages
  Memory Browser ──────────── GET /memories
  Knowledge Browser ───────── GET /knowledge/sources, /knowledge/chunks
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
                     │  ├ Knowledge Tools   │
                     │  ├ Agent Spawner     │
                     │  ├ Skills            │
                     │  ├ Templates         │
                     │  ├ Discovery         │
                     │  ├ Capabilities      │
                     │  └ Orchestration     │
                     ├────────────────────┤
                     │  Memory System      │
                     │  ├ ChromaDB Store    │
                     │  ├ Context Manager   │
                     │  ├ Fact Extractor    │
                     │  └ Decay Strategy    │
                     ├────────────────────┤
                     │  Knowledge Base     │
                     │  ├ Markdown Chunker  │
                     │  ├ ChromaDB Index    │
                     │  └ Semantic Search   │
                     ├────────────────────┤
                     │  Event Bus (SQLite)  │
                     └────────────────────┘
```

## Key Features

### Agent Runtime
Core loop: human prompt → context assembly (memory recall, knowledge retrieval) → LLM request → response parsing → tool call loop and/or sub-agent spawn → fact extraction → final response. Configurable per-agent: model, temperature, system prompt, allowed tools, iteration limits, HITL policy, retry settings.

### Agent Templates
Pre-defined agent roles with specialized prompts, tool access, and configurations:

| Template | Purpose | Tool Access |
|----------|---------|-------------|
| `coder` | Autonomous Python build agent (7-phase TDD workflow) | filesystem, shell |
| `researcher` | Deep research with structured output | none (pure reasoning) |
| `writer` | Polished text production from research | none |
| `editor` | Text review and improvement | none |
| `critic` | Structured critique with PASS/FAIL verdict | none |
| `capability-acquirer` | Discovers and acquires new capabilities | all |
| `hitl-worker` | Generic worker with human approval | all |
| `non-hitl-worker` | Generic worker, fully autonomous | all |

Agents discover templates via `list_templates(query="...")` semantic search.

### Skills
Reusable prompt templates loaded from `skills/*.md` files. Agents can:
- **Discover:** `list_skills(query="...")` — semantic search over skill descriptions
- **Test:** `test_skill(template, description, test_args)` — dry-run with LLM evaluation (PASS/FAIL)
- **Create:** `create_skill(name, template, description)` — writes a new skill file with deduplication check
- **Update:** `update_skill(name, template)` — versions the old file, writes new content

### Knowledge Base
Markdown documents are automatically chunked by heading, embedded, and stored in ChromaDB for semantic retrieval. The knowledge base is ingested on startup from the `knowledgeDir` directory. Agents search it via `search_knowledge(query="...")`. The UI provides a tree-structured browser with semantic search.

### Orchestration
Task decomposition and multi-strategy execution:
- **Sequential** — subtasks run in order
- **Parallel** — independent subtasks run concurrently
- **Pipeline** — each subtask's output feeds into the next
- Per-subtask failure policies: retry, skip, escalate, reassign

### Memory System
Three-layer memory with automatic lifecycle:
- **Context memory** — within a conversation, with token-aware pruning
- **Semantic memory** — cross-conversation fact storage in ChromaDB, with importance scoring and decay
- **Fact extraction** — automatic extraction of key facts from conversations via LLM

### Per-Agent Tool Scoping
Each agent can be configured with `allowed_mcp_servers` and `allowed_tools` to restrict which tools it sees, reducing token cost and enforcing least-privilege access.

### Unified Capability Discovery
RAG-based discovery across all capability dimensions via `discover(query="...")`:
- Skills, agent templates, MCP server tools, knowledge chunks, and memories — all searchable from a single tool.

### Inter-Agent Communication
Message bus for agents to exchange typed messages (task, result, question, answer, guidance, status_update). Parent agents can spawn sub-agents, delegate tasks, and collect results.

### Human in the Loop (HITL)
Configurable approval gates: `always_ask`, `dangerous_only`, or `never`. The HITL panel in the UI shows pending requests with approve/deny controls and optional feedback messages.

### Observability
Every significant action emits an event via the EventBus (LLM requests/responses, tool calls/results, memory reads/writes, agent spawns, HITL events, errors). Events are persisted in SQLite and streamed via SSE. The UI provides:
- **Per-agent event timeline** — on the agent detail page
- **Global event inspector** — filterable by event type, module, and source agent
- **Cost tracking** — per-agent and platform-wide LLM cost summaries

### MCP Server Integration
Agents connect to Model Context Protocol servers for external tool access. Servers are configured in `lyra.config.json` and can be stdio or HTTP/SSE transport. Agent-managed servers can be created at runtime.

## User Testing / Showcase Guide

Open the UI at `http://localhost:3000`. Use cases are in `docs/agent-drive/`:

| UC | Title | What it showcases |
|----|-------|-------------------|
| [UC-001](docs/agent-drive/UC-001-greeting-memory.md) | Greeting & Memory | Basic chat, auto-extraction, memory recall |
| [UC-002](docs/agent-drive/UC-002-hitl-approval-flow.md) | HITL Approval Flow | Human-in-the-loop approve/deny gates |
| [UC-003](docs/agent-drive/UC-003-tool-system.md) | Tool System | MCP filesystem/shell tools, skills |
| [UC-004](docs/agent-drive/UC-004-memory-system.md) | Memory System | Semantic memory, context management, decay |
| [UC-005](docs/agent-drive/UC-005-multi-agent-orchestration.md) | Multi-Agent Orchestration | Task decomposition, sub-agent spawning |
| [UC-006](docs/agent-drive/UC-006-inter-agent-communication.md) | Inter-Agent Communication | Message bus, typed messages between agents |
| [UC-007](docs/agent-drive/UC-007-orchestration-patterns.md) | Orchestration Patterns | Sequential, parallel, pipeline execution |
| [UC-008](docs/agent-drive/UC-008-per-agent-tool-scoping.md) | Per-Agent Tool Scoping | MCP server filtering, tool whitelists |
| [UC-009](docs/agent-drive/UC-009-graph-view.md) | Graph View | Agent topology and orchestration visualization |
| [UC-010](docs/agent-drive/UC-010-orchestration-subtask-dispatch.md) | Subtask Dispatch | Orchestration with real sub-agent execution |
| [UC-011](docs/agent-drive/UC-011-skill-creation-lifecycle.md) | Skill Creation Lifecycle | Search, test, create, dedup, version, update |
| [UC-012](docs/agent-drive/UC-012-mcp-server-management.md) | MCP Server Management | Runtime server creation and connection |
| [UC-013](docs/agent-drive/UC-013-learning-reflection-patterns.md) | Learning & Reflection | Agent self-analysis and pattern recognition |
| [UC-014](docs/agent-drive/UC-014-knowledge-base-and-cleanup.md) | Knowledge Base | Document ingestion, semantic search, cleanup |

Use cases can be run via the UI manually or driven programmatically via the API by Claude Code (see `docs/agent-drive/README.md`).

## Project Structure

```
lyra-seed/
├── backend/              # FastAPI + Python
│   ├── src/agent_platform/
│   │   ├── api/          # Routes, deps, main app factory
│   │   ├── core/         # Runtime, models, config
│   │   ├── db/           # SQLite repositories, vector store
│   │   ├── llm/          # OpenRouter provider, embeddings, retry
│   │   ├── memory/       # ChromaDB store, context manager, extractor, decay
│   │   ├── knowledge/    # Document chunker, ChromaDB knowledge store
│   │   ├── observation/  # Event bus, event store, cost tracker
│   │   ├── orchestration/# Task decomposition, strategies, synthesis
│   │   └── tools/        # MCP client, registry, spawner, skills, templates,
│   │                     #   discovery, capabilities, agent lifecycle/messaging
│   └── tests/smoke/      # 192 smoke tests across 22 phases
├── frontend/             # Next.js + React + TypeScript
│   ├── src/app/          # Pages: agents, memories, knowledge, events, graph, config
│   ├── src/components/   # UI components (detail, messages, graph, HITL)
│   ├── src/hooks/        # SSE event stream, graph data hooks
│   └── src/lib/          # API client
├── prompts/              # Agent prompt templates
│   ├── default.md/json   # Default agent config
│   ├── coder.md/json     # Autonomous Python build agent
│   ├── researcher.md/json# Deep research agent
│   ├── writer.md/json    # Text production agent
│   ├── editor.md/json    # Text editing agent
│   ├── critic.md/json    # Structured critique agent
│   ├── capability-acquirer.md/json # Capability acquisition agent
│   ├── *-worker.md/json  # Worker templates (HITL / non-HITL)
│   └── system/           # Internal prompts (extraction, summarization, evaluation)
├── skills/               # Skill files (.md with YAML frontmatter)
│   ├── summarize.md      # Summarize text into bullet points
│   ├── translate.md      # Translate text to target language
│   └── code-review.md    # Review code for quality and bugs
├── knowledge/            # Knowledge base documents (.md, auto-ingested on startup)
│   ├── lyra-*.md         # Platform documentation (API, config, memory, etc.)
│   ├── *-models.md       # LLM model reference docs (Claude, GPT, Gemini, etc.)
│   └── model-comparison.md # Cross-provider model comparison
├── mcp-servers/          # MCP server implementations
│   └── microblog-api/    # Example: microblog API server
├── data/                 # Runtime data (gitignored)
│   ├── lyra.db           # SQLite (agents, conversations, events, messages)
│   ├── memory/           # ChromaDB persistent memory storage
│   └── knowledge_index/  # ChromaDB persistent knowledge index
├── docs/                 # Project documentation
│   ├── ROADMAP.md        # Full version/phase roadmap
│   ├── REQUIREMENTS.md   # Requirements with delivery status
│   ├── DEVELOPMENT_METHODOLOGY.md # Phase-driven smoke-test workflow
│   ├── CONFIGURATION_GUIDE.md # All configuration surfaces
│   ├── BACKLOG.md        # Future work items
│   ├── agent-drive/      # 14 use cases with execution reports
│   └── phases/           # Per-phase plans, tests, status
├── lyra.config.json      # Platform configuration
├── .env                  # Secrets (gitignored)
└── justfile              # Task runner recipes
```

## Current Status

- **V1 Complete:** 8 phases — skeleton, events, runtime, tools, memory, UI, HITL, hardening
- **V2 Complete:** 7 phases — spawning, messaging, orchestration, tool scoping, graph UI, subtask dispatch, skills
- **V3 Complete:** 4 phases — skill lifecycle, MCP server creation, capability acquisition, learning & reflection
- **V4 Complete:** 3 phases — technical alignment, RAG knowledge base, unified capability discovery
- **192 smoke tests** all passing across 22 phases

## Documentation

- [Roadmap](docs/ROADMAP.md) — Full version/phase plan
- [Requirements](docs/REQUIREMENTS.md) — Feature specifications with delivery status
- [Configuration Guide](docs/CONFIGURATION_GUIDE.md) — All configuration surfaces with examples
- [Development Methodology](docs/DEVELOPMENT_METHODOLOGY.md) — Phase-driven smoke-test workflow
- [Agent Templates](prompts/README.md) — Template descriptions and composition patterns
- [Project Assessment](docs/PROJECT_ASSESSMENT.md) — What's standard vs cutting-edge
- [Post-V3 Roadmap](docs/POST_V3_ROADMAP.md) — V4 proposals and technical debt
- [Backlog](docs/BACKLOG.md) — Future work items
