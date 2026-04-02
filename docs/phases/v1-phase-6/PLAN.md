# V1 Phase 6 — Plan

## Phase Reference
- **Version:** V1
- **Phase:** 6
- **Title:** Pre-V2 Hardening
- **Scope:** LLM retry with backoff, HITL timeout, memory GC, context compression, cost tracking

## Prerequisites
- [x] V1 Phase 0: Project Skeleton & Tooling — COMPLETE
- [x] V1 Phase 1: Abstractions & Event System — COMPLETE
- [x] V1 Phase 2: Agent Runtime — COMPLETE
- [x] V1 Phase 3: Tool System — COMPLETE
- [x] V1 Phase 4: Memory System — COMPLETE
- [x] V1 Phase 5: Observation UI — COMPLETE

## Deliverables Checklist

### 6.1 — LLM Retry with Exponential Backoff
- [x] `async_retry` and `sync_retry` helpers with configurable max_retries, base_delay, max_delay
- [x] Retries on HTTP 429 (rate limit), 502/503/504 (gateway errors), and `httpx.TimeoutException`
- [x] Exponential backoff with jitter to avoid thundering herd
- [x] Integrated into both OpenRouterProvider and OpenRouterEmbeddingProvider
- [x] Timeout configuration: 60s read, 10s connect on all httpx clients

### 6.2 — HITL Timeout & Stuck Agent Cleanup
- [x] `AgentConfig.hitl_timeout_seconds: float = 300` — configurable per-agent
- [x] On timeout: agent status set to IDLE, HITL_RESPONSE event emitted with `timed_out: True`, tool call treated as denied
- [x] `AgentRuntime.cleanup_stuck_agents()` — called on startup, resets RUNNING/WAITING_HITL agents to IDLE

### 6.3 — Memory Garbage Collection
- [x] `TimeDecayStrategy` wired into `ChromaMemoryStore.update_access()` — decay scores recomputed on access
- [x] `ChromaMemoryStore.prune(agent_id, threshold, max_entries)` — deletes low-score entries and enforces max count
- [x] Called automatically after each successful agent run via `AgentRuntime._prune_memories()`
- [x] MEMORY_WRITE event emitted with `action: gc_prune` when entries are pruned

### 6.4 — Context Compression (Token Estimation + Truncation)
- [x] `estimate_tokens(text)` — heuristic `len(text) // 4` (~4 chars per token)
- [x] `estimate_messages_tokens(messages)` — sum + 4 tokens per-message overhead
- [x] `ContextManager.max_context_tokens = 100_000` — configurable token budget
- [x] Sliding window truncation: removes oldest non-system messages when over budget
- [x] Inserts `[Earlier conversation history truncated for context limits]` marker

### 6.5 — Cost Tracking
- [x] Model cost lookup table with pricing for common OpenAI and Anthropic models, plus fallback
- [x] `compute_agent_cost(event_bus, agent_id)` — aggregates token usage from LLM_RESPONSE events
- [x] `compute_total_cost(event_bus)` — aggregates across all agents
- [x] Returns: `total_prompt_tokens`, `total_completion_tokens`, `total_cost_usd`, `by_model` breakdown
- [x] API endpoints: `GET /agents/{agent_id}/cost` and `GET /cost`

## Implementation Steps

### Step 1: Retry helpers
- Create `llm/retry.py` with `async_retry` and `sync_retry` wrappers
- Integrate into `openrouter.py` and `openrouter_embeddings.py`
- **Files:** `backend/src/agent_platform/llm/retry.py` (new), `llm/openrouter.py`, `llm/openrouter_embeddings.py`

### Step 2: HITL timeout and stuck agent cleanup
- Add `hitl_timeout_seconds` to AgentConfig
- Implement `asyncio.wait_for` in HITL gate
- Add `cleanup_stuck_agents()` to runtime, call from lifespan
- **Files:** `core/models.py`, `core/runtime.py`, `api/main.py`

### Step 3: Memory garbage collection
- Wire `TimeDecayStrategy` into `ChromaMemoryStore.update_access()`
- Implement `ChromaMemoryStore.prune(agent_id, threshold, max_entries)`
- Call prune after each agent run in runtime
- **Files:** `memory/chroma_memory_store.py`, `core/runtime.py`

### Step 4: Context compression
- Create `memory/token_estimator.py` with heuristic token estimation
- Integrate into `ContextManager` with configurable budget and sliding window
- **Files:** `memory/token_estimator.py` (new), `memory/context_manager.py`

### Step 5: Cost tracking
- Create `observation/cost_tracker.py` with model pricing and aggregation
- Add API endpoints to observation_routes
- **Files:** `observation/cost_tracker.py` (new), `api/observation_routes.py`

## File Manifest

### New Files
- `backend/src/agent_platform/llm/retry.py` — async + sync retry with exponential backoff
- `backend/src/agent_platform/memory/token_estimator.py` — heuristic token estimation
- `backend/src/agent_platform/observation/cost_tracker.py` — cost aggregation from events
- `backend/tests/smoke/test_v1_phase_6.py` — 10 smoke tests

### Modified Files
- `backend/src/agent_platform/llm/openrouter.py` — retry integration
- `backend/src/agent_platform/llm/openrouter_embeddings.py` — retry integration
- `backend/src/agent_platform/core/models.py` — hitl_timeout_seconds, memoryGC config, context config
- `backend/src/agent_platform/core/runtime.py` — HITL timeout, memory prune, stuck agent cleanup
- `backend/src/agent_platform/memory/chroma_memory_store.py` — prune method, decay on access
- `backend/src/agent_platform/memory/context_manager.py` — token budget + truncation
- `backend/src/agent_platform/api/main.py` — cleanup_stuck_agents on startup
- `backend/src/agent_platform/api/observation_routes.py` — cost API endpoints

## Risks & Decisions
- **Token estimation heuristic:** Using `len(text) // 4` instead of tiktoken to avoid a heavy dependency. Sufficient for budget guardrails.
- **HITL timeout → IDLE (not FAILED):** Human not responding is not a system error. Agent returns to IDLE and can be re-prompted.
- **Prune after every run:** Lightweight operation; avoids needing a background scheduler.
- **Cost pricing table:** Model costs configured in `lyra.config.json` for easy updates without code changes.
