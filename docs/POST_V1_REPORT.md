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

---

## 12. Phase 7: Memory Enhancement

Phase 7 upgraded the memory system with LLM-based summarization, automatic fact extraction, and cross-agent memory sharing. **70/70 smoke tests pass** (55 previous + 15 new).

### 12.1 Cross-Agent Memory with Visibility Model

**Files:** `memory/models.py`, `memory/chroma_memory_store.py`, `memory/memory_tools.py`

- `MemoryVisibility` enum: PRIVATE, TEAM, PUBLIC, INHERIT
  - PRIVATE: only the owning agent can see the memory
  - PUBLIC: visible to all agents via cross-agent search
  - TEAM: resolves to PUBLIC until V2 adds parent-child agent hierarchy
  - INHERIT: reserved for V2
- `MemoryEntry.visibility` field (default PRIVATE, backward compatible with existing entries)
- Default visibility by memory type:
  - **PUBLIC**: FACT, PROCEDURE, TOOL_KNOWLEDGE, DOMAIN_KNOWLEDGE (shared knowledge)
  - **PRIVATE**: EPISODIC, PREFERENCE, DECISION, OUTCOME (agent-specific)
- `ChromaMemoryStore.search(include_public=True)` uses ChromaDB `$or` filter: `[{agent_id: own}, {visibility: public}, {visibility: team}]`
- `remember` tool accepts explicit `visibility` parameter; `recall` tool defaults to `include_public=True`
- Context injection (`ContextManager.assemble()`) now includes PUBLIC memories from other agents, marked as `[shared]` in the injection message

### 12.2 Context Summarization (Replaces Truncation)

**Files:** `memory/summarizer.py` (new), `memory/context_manager.py`, `prompts/system/summarize.md` (new)

- `ContextSummarizer(llm_provider, summary_model, system_prompt)` — calls LLM to summarize messages that would otherwise be dropped
- When the conversation exceeds the token budget:
  1. Identifies oldest non-system messages to remove (same logic as previous truncation)
  2. If `llm_provider` is configured: calls LLM to summarize the dropped messages
  3. Saves the summary as an EPISODIC memory in ChromaDB (importance=0.6, visibility=PRIVATE)
  4. Injects `[Summary of N earlier messages: ...]` as a system message
  5. If no LLM provider: falls back to old `[Earlier conversation truncated]` marker (backward compatible)
- Configurable `summaryModel` per agent (defaults to cheap model like `gpt-4.1-nano`)
- System prompt loaded from `prompts/system/summarize.md` — editable without code changes

### 12.3 Automatic Fact Extraction

**Files:** `memory/extractor.py` (new), `core/runtime.py`, `prompts/system/extract_facts.md` (new)

- `FactExtractor(llm_provider, extraction_model, memory_store, event_bus, system_prompt)` — after each agent turn, extracts facts/preferences/decisions from the response
- Extraction flow:
  1. After the agent produces a final response (no tool calls), if `auto_extract=True`
  2. Sends the last 6 messages + assistant response to the extraction LLM
  3. LLM returns JSON array: `[{content, memory_type, importance}]`
  4. Each item is stored as a `MemoryEntry` with visibility from `memory_sharing` config
  5. `MEMORY_WRITE` events emitted with `source: auto_extract`
  6. Failures are silently caught — extraction never breaks the agent run
- Configurable `extractionModel` per agent (separate from summary model)
- System prompt loaded from `prompts/system/extract_facts.md`
- Toggleable per agent via `auto_extract: bool` in config

### 12.4 Externalized System Prompts

**Files:** `prompts/system/summarize.md`, `prompts/system/extract_facts.md`, `core/platform_config.py`

- All internal LLM prompts (summarization, extraction) stored as editable `.md` files in `prompts/system/`
- `load_system_prompt(name, project_root)` helper loads `prompts/system/{name}.md`, returns `None` if missing (falls back to hardcoded default)
- Loaded once on app startup, passed to `ContextSummarizer` and `FactExtractor` at construction
- Version-controllable, editable without touching Python code

### 12.5 Configuration

All new parameters follow the standard four-level resolution chain (documented in DEVELOPMENT_METHODOLOGY.md §11):

| Parameter | `lyra.config.json` | `prompts/default.json` | `prompts/{name}.json` | Hardcoded |
|---|---|---|---|---|
| `summaryModel` | platform default | per-agent default | per-agent override | `openai/gpt-4.1-nano` |
| `extractionModel` | platform default | per-agent default | per-agent override | `openai/gpt-4.1-nano` |
| `auto_extract` | — | `true` | per-agent override | `false` |
| `memory_sharing` | — | type→visibility map | per-agent override | DEFAULT_VISIBILITY dict |

### 12.6 Updated Memory Layer Definitions

| Layer | Scope | Storage | Key Feature |
|-------|-------|---------|-------------|
| **Context** | Single conversation | In-memory messages | LLM summarization when over token budget; summaries saved as EPISODIC memories |
| **Cross-context** | Per agent, across sessions | ChromaDB (PRIVATE) | Autobiographical: EPISODIC, PREFERENCE, DECISION, OUTCOME. Auto-extracted after each turn. |
| **Cross-agent** | All agents | ChromaDB (PUBLIC) | Shared knowledge: FACT, PROCEDURE, TOOL_KNOWLEDGE, DOMAIN_KNOWLEDGE. Visible to all agents via `include_public` search. |

### 12.7 Updated Phase Status

| Phase | Title | Smoke Tests |
|-------|-------|-------------|
| V1 Phase 0 | Project Skeleton & Tooling | 5/5 |
| V1 Phase 1 | Abstractions & Event System | 9/9 |
| V1 Phase 2 | Agent Runtime | 9/9 |
| V1 Phase 3 | Tool System | 7/7 |
| V1 Phase 4 | Memory System | 7/7 |
| V1 Phase 5 | Observation UI | 8/8 |
| V1 Phase 6 | Pre-V2 Hardening | 10/10 |
| V1 Phase 7 | Memory Enhancement | 15/15 |
| **Total** | | **70/70** |

### 12.8 Previously Missing Items — Status After Phase 7

| Feature | Before Phase 7 | After Phase 7 |
|---------|---------------|---------------|
| Context summarization | Simple truncation (drop old messages) | Done — LLM summarization, summaries saved as memories |
| Auto session summaries | Not implemented | Done — automatic fact extraction after each turn |
| Cross-agent memory | All memories agent-siloed | Done — PUBLIC visibility for knowledge types |
| Memory visibility model | No visibility concept | Done — PRIVATE/TEAM/PUBLIC/INHERIT enum |
| Externalized prompts | Prompts hardcoded in Python | Done — `prompts/system/*.md` files |
| Embedding caching | Not implemented | Still not implemented (low priority) |
| Docker deployment | Not implemented | Still not implemented |
| RAG | Not implemented | Deferred to V2/V4 |

---

## 13. V2 Progress Report

### V2 Phase 1: Sub-Agent Spawning — COMPLETE (14 tests)

Delivered synchronous sub-agent spawning, then upgraded to full AgentRuntime execution for children (tools, memory, iteration loop). Spawn depth guard (max 3) prevents infinite recursion. Template-based config inheritance from `prompts/{name}.json`.

### V2 Phase 2: Inter-Agent Communication & Async Lifecycle — COMPLETE (14+2 tests)

**Async Spawning:**
- `spawn_agent` returns immediately, child runs in background `asyncio.Task`
- `wait_for_agent` blocks with timeout via `asyncio.Event`
- `check_agent_status` for non-blocking status checks
- `stop_agent` cancels running children
- `dismiss_agent` marks children as COMPLETED
- Background task cleanup on shutdown

**Message Bus:**
- `AgentMessage` model with 6 types: TASK, RESULT, QUESTION, ANSWER, GUIDANCE, STATUS_UPDATE
- `SqliteMessageRepo` with inbox/sent/between queries
- `send_message` / `receive_messages` tools
- MESSAGE_SENT / MESSAGE_RECEIVED events
- Auto-wake: idle agents auto-start a turn on TASK/GUIDANCE messages
- Consumed messages deleted after processing
- Workers auto-instructed to send results back via `send_message`

**Runtime Integration:**
- GUIDANCE messages injected into conversation context each iteration
- All V2P2 tools get agent_id auto-injected (prevents LLM hallucinating IDs)

**UI:**
- MessagePanel: scrollable message list with type badges, direction indicators, send input
- SUB-AGENTS bar on parent detail page with clickable child chips
- PARENT link on child detail page for upward navigation
- Memory browser at /memories with semantic search and filtering

**Key Fixes During Testing:**
- Empty tool-calling turns hidden from conversation display
- Platform config reloads from disk on each agent creation
- Memory deduplication (cosine similarity threshold)
- Auto-wake sender resolves to parent_agent_id, not "default"

### Current Test Suite: 98 backend + 6 frontend = 104 total smoke tests
