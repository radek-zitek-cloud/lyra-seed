# Post-V1 Report — Self-Evolving Multi-Agent Platform

> **Date:** 2026-04-02
> **Status:** V1 Complete (all 6 phases, 45 smoke tests passing)
> **Author:** Claude Code (implementation) / Radek Zitek (direction)

---

## 1. Executive Summary

V1 is **complete and functional**. The platform delivers a single-agent system that converses with a human via LLM (OpenRouter), calls tools (MCP servers + prompt macros), remembers across sessions (ChromaDB semantic memory), and exposes its full execution trace in a real-time web UI. All original V1 exit criteria are met, with several pragmatic technology upgrades over the original roadmap.

---

## 2. Phase Completion Status

| Phase | Title | Status | Smoke Tests |
|-------|-------|--------|-------------|
| V1 Phase 0 | Project Skeleton & Tooling | COMPLETE | 5/5 |
| V1 Phase 1 | Abstractions & Event System | COMPLETE | 9/9 |
| V1 Phase 2 | Agent Runtime | COMPLETE | 9/9 |
| V1 Phase 3 | Tool System | COMPLETE | 7/7 |
| V1 Phase 4 | Memory System | COMPLETE | 7/7 |
| V1 Phase 5 | Observation UI | COMPLETE | 8/8 |
| **Total** | | **All COMPLETE** | **45/45** |

---

## 3. What Was Built

### 3.1 Backend Architecture

```
backend/src/agent_platform/
├── api/                          # FastAPI routes + SSE streaming
│   ├── main.py                   # App factory, lifespan, dependency wiring
│   ├── routes.py                 # Agent CRUD, prompt, HITL endpoints
│   ├── observation_routes.py     # Event/conversation/tool query endpoints
│   ├── macro_routes.py           # Prompt macro CRUD endpoints
│   ├── ws_routes.py              # SSE real-time event streaming
│   └── _deps.py                  # Dependency access for routes
├── core/
│   ├── runtime.py                # AgentRuntime — core agent loop
│   ├── models.py                 # Agent, Conversation, AgentConfig, HITLPolicy
│   ├── config.py                 # Pydantic settings (env vars)
│   ├── platform_config.py        # lyra.config.json loader + agent file config
│   └── strategy.py               # Strategy[TInput, TOutput] protocol
├── llm/
│   ├── provider.py               # LLMProvider protocol
│   ├── openrouter.py             # OpenRouter LLM implementation
│   ├── openrouter_embeddings.py  # OpenRouter embedding provider (dual sync/async)
│   ├── embeddings.py             # EmbeddingProvider protocol
│   └── models.py                 # Message, ToolCall, LLMResponse, LLMConfig
├── memory/
│   ├── chroma_memory_store.py    # ChromaDB-backed semantic memory
│   ├── context_manager.py        # Memory injection into conversation context
│   ├── memory_tools.py           # remember/recall/forget as agent tools
│   ├── decay.py                  # TimeDecayStrategy
│   ├── fake_embeddings.py        # Deterministic test embeddings
│   └── models.py                 # MemoryEntry, MemoryType
├── tools/
│   ├── provider.py               # ToolProvider protocol
│   ├── registry.py               # ToolRegistry — aggregation + routing
│   ├── mcp_client.py             # Real stdio JSON-RPC MCP transport
│   ├── mcp_provider.py           # Mock MCP provider for testing
│   ├── prompt_macro.py           # PromptMacro model + provider
│   └── models.py                 # Tool, ToolType, ToolResult
├── observation/
│   ├── events.py                 # Event, EventType, EventFilter
│   ├── event_bus.py              # EventBus protocol
│   ├── in_process_event_bus.py   # Async queue + SQLite persistence
│   └── sqlite_event_store.py     # Event table, insert, query
└── db/
    ├── repository.py             # Repository[T] protocol
    ├── vector_store.py           # VectorStore protocol
    ├── sqlite_agent_repo.py      # Agent CRUD
    ├── sqlite_conversation_repo.py # Conversation CRUD
    └── sqlite_macro_repo.py      # Prompt macro CRUD
```

### 3.2 Frontend Architecture

```
frontend/src/
├── app/
│   ├── layout.tsx                # Root layout (header, nav, footer)
│   ├── page.tsx                  # Home — agent list + create form
│   ├── globals.css               # Dark terminal theme, animations
│   └── agents/[id]/page.tsx      # Agent detail — conversation, events, tools, HITL
├── components/
│   ├── AgentDetail.tsx           # ConversationPanel + EventTimeline
│   ├── AgentList.tsx             # Agent card grid with status badges
│   ├── PromptInput.tsx           # Message input with auto-refocus
│   ├── HITLPanel.tsx             # Inline approve/deny controls
│   ├── ToolInspector.tsx         # Tool call/result pair display
│   └── ConnectionStatus.tsx      # LIVE/CONNECTING/OFFLINE indicator
├── hooks/
│   └── useEventStream.ts         # SSE connection with auto-reconnect
└── lib/
    └── api.ts                    # API client functions
```

### 3.3 Configuration

| File | Scope | Contents |
|------|-------|---------|
| `.env` | Secrets + server bind | `LYRA_OPENROUTER_API_KEY`, `LYRA_HOST`, `LYRA_PORT` |
| `lyra.config.json` | Platform config | `mcpServers`, `dataDir`, `defaultModel`, `embeddingModel`, `systemPromptsDir` |
| `prompts/{name}.md` | Agent system prompts | Markdown prompt per agent (fallback: `default.md`) |
| `prompts/{name}.json` | Agent config overrides | model, temperature, hitl_policy, max_iterations |

### 3.4 API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| POST | `/agents` | Create agent |
| GET | `/agents` | List agents |
| GET | `/agents/{id}` | Get agent details |
| DELETE | `/agents/{id}` | Delete agent |
| POST | `/agents/{id}/prompt` | Send message to agent |
| POST | `/agents/{id}/hitl-respond` | Approve/deny HITL gate |
| GET | `/agents/{id}/events` | Query agent events (filterable) |
| GET | `/agents/{id}/conversations` | Get conversation history |
| GET | `/agents/{id}/events/stream` | SSE real-time event stream |
| GET | `/events/stream` | SSE global event stream |
| GET | `/tools` | List all registered tools |
| GET | `/tools/{name}/calls` | Tool call history |
| POST | `/macros` | Create prompt macro |
| GET | `/macros` | List macros |
| GET | `/macros/{id}` | Get macro |
| PUT | `/macros/{id}` | Update macro |
| DELETE | `/macros/{id}` | Delete macro |

---

## 4. Technology Deviations from Roadmap

| Aspect | Roadmap Specified | Actually Implemented | Why |
|--------|-------------------|---------------------|-----|
| Vector storage | sqlite-vec | **ChromaDB** (PersistentClient) | sqlite-vec has cross-platform installation issues; ChromaDB handles embeddings + metadata filtering natively, runs in-process with SQLite backing |
| Real-time streaming | WebSocket | **SSE** (Server-Sent Events) | WebSocket connections caused shutdown hangs (background tasks never completing on uvicorn reload); SSE uses normal HTTP StreamingResponse with clean lifecycle |
| Configuration | Env vars via Pydantic BaseSettings | **Env + JSON + filesystem** | Secrets stay in env vars; platform config (MCP servers, models) in `lyra.config.json`; agent prompts and config overrides on filesystem for version control |
| MCP client | Implied stub/basic | **Full stdio JSON-RPC** transport | Enables immediate real-world use with MCP ecosystem servers (filesystem, shell, etc.) |
| Embedding provider | Behind abstract interface | **Dual sync/async** implementation | ChromaDB calls embedding functions synchronously; needed both sync httpx.Client and async httpx.AsyncClient |
| Database migrations | Alembic | **Auto-created schemas** | Sufficient for single-dev V1; Alembic can be added when schema evolution becomes complex |

---

## 5. Features Added Beyond Roadmap Scope

1. **Platform config system** (`lyra.config.json`): Configures MCP servers, data directory, default LLM model, embedding model, and prompts directory without code changes.

2. **Agent file-based config**: System prompts from `prompts/{name}.md`, config overrides from `prompts/{name}.json`. Falls back to `default.md`/`default.json`. Enables infrastructure-as-code patterns.

3. **Real MCP stdio transport**: Full JSON-RPC 2.0 over subprocess stdin/stdout. Windows `.cmd` resolution via `shutil.which`, Popen fallback when asyncio subprocess isn't available. Protocol handshake, tool discovery, graceful shutdown.

4. **OpenRouter embedding provider with dual interface**: Sync `httpx.Client` for ChromaDB's synchronous calls, async `httpx.AsyncClient` for protocol methods. Event emission from sync context via `loop.call_soon_threadsafe`.

5. **Event inline summaries in UI**: Event timeline shows key payload data inline — token counts for LLM calls, tool names for tool events, queries for memory reads — without needing to expand details.

6. **Smart auto-scroll**: All scrollable panes (conversation, events, tool inspector) only auto-scroll when the user is already at the bottom. Browsing history while new content arrives works without interruption.

7. **Immediate prompt display**: Human messages appear in the conversation pane instantly on send, before the agent response arrives.

---

## 6. What's Missing or Incomplete

### Not implemented (correctly deferred to V2/V3)

- Sub-agent spawning and lifecycle management (V2 Phase 1)
- Inter-agent communication and message passing (V2 Phase 2)
- Orchestration patterns (sequential, parallel, pipeline) (V2 Phase 3)
- Multi-agent UI (agent graph, message flow visualization) (V2 Phase 4)
- Agent-driven tool creation (V3)
- Capability gap analysis and acquisition (V3)
- Learning and retrospectives (V3)

### Partially implemented or simplified

| Feature | Status | Detail |
|---------|--------|--------|
| Context compression (TruncateAndSummarize) | **Simplified** | Context manager injects memories but doesn't compress/truncate old messages. Full compression requires LLM calls during context assembly — deferred. |
| Memory garbage collection | **Not implemented** | TimeDecayStrategy computes scores but no background task prunes low-score memories. Scores are stored but not acted on. |
| LLM retry with exponential backoff | **Not implemented** | OpenRouterProvider has error handling but no automatic retry logic. Single try/except only. |
| Rate limiting / token budgeting | **Not implemented** | No per-agent token budget or rate limiting on LLM calls. |
| Cost tracking | **Not implemented** | OpenRouter returns cost data in usage; it's stored in events but not aggregated or displayed. |
| Embedding caching | **Not implemented** | Roadmap mentioned "don't re-embed identical text" — not implemented. Each embedding call hits the API. |
| Pre-commit hooks (ruff, mypy) | **Not configured** | ruff and mypy are available as dev deps and justfile recipes, but no git pre-commit hook is set up. |
| Docker deployment | **Not implemented** | Roadmap mentioned docker-compose — not created. Local dev only. |
| Frontend testing | **Minimal** | Vitest configured in package.json but no frontend smoke tests written. |

---

## 7. V2 Readiness Assessment

### Architecture supports V2

The existing architecture has several V2 hooks already in place:

- **`Agent.parent_agent_id`** field exists (set to None in V1, ready for parent-child relationships)
- **`AGENT_SPAWN` and `AGENT_COMPLETE` event types** defined in EventType enum
- **ToolRegistry pattern** allows adding a `spawn_agent` tool that creates child agents
- **Event bus agent_id filtering** supports per-agent event streams (already used in SSE endpoint)
- **AgentRuntime** is instantiated once and shared — can manage multiple concurrent agent runs
- **Conversation model** is per-agent, supports independent conversation histories

### Recommended before starting V2

1. **Add LLM retry with backoff** — V2 will have more LLM calls (parent + children); failures need graceful recovery
2. **Implement memory GC** — With multiple agents creating memories, garbage collection becomes important
3. **Add cost tracking** — Multi-agent runs will multiply LLM costs; need visibility
4. **Consider agent lifecycle** — V2 needs clear semantics for agent completion, failure propagation, and cleanup
5. **Database migrations** — V2 may add new tables (agent_messages, task_decompositions); Alembic would help
6. **Evaluate context compression** — Multi-agent scenarios will hit token limits faster; TruncateAndSummarize becomes more important

### Ready to start V2?

**Yes.** All V1 foundations are solid. The abstractions (protocols, event bus, tool registry, memory store) are designed for extensibility. The recommended improvements above are enhancements, not blockers.

---

## 8. Key Files Quick Reference

### Backend core loop
- `core/runtime.py:41` — `AgentRuntime.run()` — the main agent loop
- `core/runtime.py:310` — `_hitl_gate()` — HITL pause/resume
- `core/runtime.py:376` — `_set_embedding_agent_id()` — event attribution propagation

### LLM integration
- `llm/openrouter.py:41` — `OpenRouterProvider.complete()` — LLM API call
- `llm/openrouter_embeddings.py:76` — `_call_api_sync()` — embedding API (sync, for ChromaDB)

### Memory system
- `memory/chroma_memory_store.py:66` — `search()` — semantic similarity search
- `memory/context_manager.py:26` — `assemble()` — memory injection into context
- `memory/memory_tools.py:112` — `_remember()` — store a memory

### Tool system
- `tools/registry.py:32` — `call_tool()` — route to correct provider
- `tools/mcp_client.py:155` — `MCPStdioClient.connect()` — MCP server handshake
- `tools/prompt_macro.py:53` — `call_tool()` — template expansion + LLM sub-call

### Event system
- `observation/in_process_event_bus.py:50` — `emit()` — broadcast + persist
- `observation/in_process_event_bus.py:95` — `_iter_subscription()` — async event iterator

### App wiring
- `api/main.py:57` — `create_app()` — factory that wires all components
- `api/main.py:150` — lifespan — startup/shutdown sequence

---

## 9. Dependency Summary

### Backend (Python 3.12+)
| Package | Purpose |
|---------|---------|
| fastapi | Web framework |
| uvicorn[standard] | ASGI server |
| pydantic + pydantic-settings | Data models + env config |
| httpx | Async/sync HTTP client (OpenRouter API) |
| aiosqlite | Async SQLite (events, agents, conversations, macros) |
| chromadb | Vector database (semantic memory) |
| pytest + pytest-asyncio | Test framework |
| ruff | Linter + formatter |

### Frontend (Node.js)
| Package | Purpose |
|---------|---------|
| next 15.3.1 | React framework |
| react 19.1.0 | UI library |
| tailwindcss 4.2.2 | CSS framework |
| vitest | Test runner |

---

## 10. Running the Platform

```bash
# Install dependencies
cd backend && uv sync
cd frontend && npm install

# Start development
just dev              # Both backend + frontend
just dev-backend      # Backend only (port 8000)
just dev-frontend     # Frontend only (port 3000)

# Testing
just test             # All backend tests
just smoke-test       # All smoke tests (55 tests)
just lint             # Ruff linter
just format           # Ruff formatter

# Configuration
cp .env.example .env  # Add your LYRA_OPENROUTER_API_KEY
# Edit lyra.config.json for MCP servers, models, prompts dir
```

---

## 11. Phase 6: Pre-V2 Hardening

Phase 6 was added after the initial V1 report to harden the platform before V2 multi-agent work. **55/55 smoke tests pass** (45 original + 10 new).

### 11.1 LLM Retry with Exponential Backoff

**Files:** `llm/retry.py` (new), `llm/openrouter.py`, `llm/openrouter_embeddings.py`

- `async_retry` and `sync_retry` helpers with configurable `max_retries=3`, `base_delay=1.0`, `max_delay=30.0`
- Retries on HTTP 429 (rate limit), 502/503/504 (gateway errors), and `httpx.TimeoutException`
- Exponential backoff with jitter to avoid thundering herd
- Both OpenRouterProvider and OpenRouterEmbeddingProvider now use retry
- Timeout configuration: 60s read, 10s connect on all httpx clients

### 11.2 Agent Lifecycle: HITL Timeout + Stuck Agent Cleanup

**Files:** `core/models.py`, `core/runtime.py`, `api/main.py`

- `AgentConfig.hitl_timeout_seconds: float = 300` — configurable per-agent HITL gate timeout
- On timeout: agent status set to IDLE (not FAILED — human didn't respond, not a system error), HITL_RESPONSE event emitted with `timed_out: True`, tool call treated as denied
- `AgentRuntime.cleanup_stuck_agents()` — called on startup, resets any agents stuck in RUNNING or WAITING_HITL to IDLE (crash recovery)

### 11.3 Memory Garbage Collection

**Files:** `memory/chroma_memory_store.py`, `core/runtime.py`

- `TimeDecayStrategy` (existed since Phase 4) now wired into `ChromaMemoryStore.update_access()` — decay scores recomputed on every memory access
- `ChromaMemoryStore.prune(agent_id, threshold=0.1, max_entries=500)`:
  - Recomputes all decay scores for the agent
  - Deletes entries with decay_score below threshold
  - Enforces max_entries limit by removing lowest-scored entries
  - Returns count of deleted entries
- Called automatically after each successful agent run via `AgentRuntime._prune_memories()`
- MEMORY_WRITE event emitted with `action: gc_prune` when entries are pruned

### 11.4 Context Compression: Token Estimation + Truncation

**Files:** `memory/token_estimator.py` (new), `memory/context_manager.py`

- `estimate_tokens(text)` — heuristic `len(text) // 4` (~4 chars per token for English)
- `estimate_messages_tokens(messages)` — sum + 4 tokens per-message overhead
- `ContextManager.max_context_tokens = 100_000` — configurable token budget
- Sliding window truncation: when over budget, removes oldest non-system messages while preserving system prompts and the current query
- Inserts `[Earlier conversation history truncated for context limits]` marker when truncation occurs

### 11.5 Cost Tracking

**Files:** `observation/cost_tracker.py` (new), `api/observation_routes.py`

- `MODEL_COSTS` lookup table with pricing for common OpenAI and Anthropic models, plus a default fallback
- `compute_agent_cost(event_bus, agent_id)` — aggregates `prompt_tokens` and `completion_tokens` from all LLM_RESPONSE events for an agent, applies model-specific pricing
- `compute_total_cost(event_bus)` — same across all agents
- Returns: `total_prompt_tokens`, `total_completion_tokens`, `total_cost_usd`, `by_model` breakdown (tokens, cost, call count per model)
- API endpoints: `GET /agents/{agent_id}/cost` and `GET /cost`

### 11.6 Updated Phase Status

| Phase | Title | Smoke Tests |
|-------|-------|-------------|
| V1 Phase 0 | Project Skeleton & Tooling | 5/5 |
| V1 Phase 1 | Abstractions & Event System | 9/9 |
| V1 Phase 2 | Agent Runtime | 9/9 |
| V1 Phase 3 | Tool System | 7/7 |
| V1 Phase 4 | Memory System | 7/7 |
| V1 Phase 5 | Observation UI | 8/8 |
| V1 Phase 6 | Pre-V2 Hardening | 10/10 |
| **Total** | | **55/55** |

### 11.7 Previously Missing Items — Status After Phase 6

| Feature | Before Phase 6 | After Phase 6 |
|---------|---------------|---------------|
| LLM retry with backoff | Not implemented | Done — async + sync retry, exponential backoff |
| Memory garbage collection | TimeDecayStrategy existed but unused | Done — wired, prune after each run |
| Cost tracking | Usage in events but no aggregation | Done — API endpoints with model pricing |
| HITL timeout | Could hang indefinitely | Done — configurable timeout, defaults 5min |
| Stuck agent recovery | No crash recovery | Done — cleanup on startup |
| Context compression | No token budget | Done — estimation + sliding window truncation |
| Embedding caching | Not implemented | Still not implemented (low priority) |
| Docker deployment | Not implemented | Still not implemented |
| Database migrations | Auto-create schemas | Deferred — CREATE TABLE IF NOT EXISTS sufficient for now |
