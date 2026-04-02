# V2 Phase 1 — Plan

## Phase Reference
- **Version:** V2
- **Phase:** 1
- **Title:** Sub-Agent Spawning & Lifecycle
- **Roadmap Section:** §5, V2 Phase 1

## Prerequisites
- [x] V1 Phase 0: Project Skeleton & Tooling — COMPLETE
- [x] V1 Phase 1: Abstractions & Event System — COMPLETE
- [x] V1 Phase 2: Agent Runtime — COMPLETE
- [x] V1 Phase 3: Tool System — COMPLETE
- [x] V1 Phase 4: Memory System — COMPLETE
- [x] V1 Phase 5: Observation UI — COMPLETE
- [x] V1 Phase 6: Pre-V2 Hardening — COMPLETE
- [x] V1 Phase 7: Memory Enhancement — COMPLETE

## Deliverables Checklist

### 1.1 — `spawn_agent` Tool
- [ ] `AgentSpawnerProvider` implementing `ToolProvider` protocol
- [ ] `spawn_agent` tool: creates a child agent with `parent_agent_id` set, immediately runs it with the given task
- [ ] Parameters: `name`, `task` (required); `system_prompt`, `model`, `temperature`, `allowed_tools` (optional overrides)
- [ ] Returns child agent ID and final response content
- [ ] Emits `AGENT_SPAWN` event from parent agent
- [ ] Emits `AGENT_COMPLETE` event from child agent (on success)
- [ ] Child inherits parent's config defaults unless overridden

### 1.2 — `wait_for_agent` Tool
- [ ] Blocks parent until child agent completes (status IDLE/COMPLETED/FAILED)
- [ ] Returns child's final response content
- [ ] Configurable timeout (defaults to 300s)
- [ ] Emits error if child agent not found or not a child of the caller

### 1.3 — `get_agent_result` Tool
- [ ] Retrieves the last assistant message from a child agent's conversation
- [ ] Non-blocking — returns immediately
- [ ] Returns child's status and content (or null if not yet complete)

### 1.4 — `list_child_agents` Tool
- [ ] Lists all child agents spawned by the calling agent
- [ ] Returns agent ID, name, status for each child

### 1.5 — Agent Lifecycle Events
- [ ] `AGENT_SPAWN` event emitted with payload: `{child_agent_id, child_name, task}`
- [ ] `AGENT_COMPLETE` event emitted with payload: `{parent_agent_id, content_preview}`
- [ ] Child failure emits `ERROR` event with payload including parent_agent_id

### 1.6 — Parent-Child Query Support
- [ ] `SqliteAgentRepo.list_children(parent_agent_id)` method
- [ ] API endpoint: `GET /agents/{id}/children` returns child agents

### 1.7 — Child Memory Access
- [ ] Child agents can read parent's public memories via existing cross-agent memory (include_public=True)
- [ ] No special memory isolation needed — existing visibility model handles this

## Implementation Steps

### Step 1: Agent repo — list_children query
- Add `list_children(parent_agent_id: str) -> list[Agent]` to `SqliteAgentRepo`
- Simple SQL: `SELECT * FROM agents WHERE parent_agent_id = ?`
- **Files:** `db/sqlite_agent_repo.py`

### Step 2: AgentSpawnerProvider
- Create `tools/agent_spawner.py` implementing `ToolProvider`
- Provides 4 tools: `spawn_agent`, `wait_for_agent`, `get_agent_result`, `list_child_agents`
- Constructor takes: `agent_repo`, `conversation_repo`, `llm_provider`, `event_bus`, `tool_registry`, `context_manager`, `extractor`
- `spawn_agent` implementation:
  1. Create child Agent with `parent_agent_id` set to caller's agent_id
  2. Save via agent_repo
  3. Emit AGENT_SPAWN event
  4. Run child agent via a new AgentRuntime.run() call
  5. Emit AGENT_COMPLETE event
  6. Return child ID + response content
- `wait_for_agent`: poll agent status until not RUNNING
- `get_agent_result`: fetch last assistant message from child's conversation
- `list_child_agents`: query agent_repo.list_children()
- **Files:** `tools/agent_spawner.py` (new)

### Step 3: Wire into app factory
- Create `AgentSpawnerProvider` in `create_app()` after runtime is created
- Register with `tool_registry`
- Pass required dependencies
- **Files:** `api/main.py`

### Step 4: API endpoint for child agents
- Add `GET /agents/{agent_id}/children` to routes
- Returns list of child agents
- **Files:** `api/routes.py`

### Step 5: Agent_id injection for spawner tools
- Runtime already injects `agent_id` into memory tools
- Same pattern needed for spawner tools (agent_id tells the spawner who the parent is)
- **Files:** `core/runtime.py`

## Dependencies & Libraries
- No new dependencies — all functionality uses existing infrastructure

## File Manifest

### New Files
- `backend/src/agent_platform/tools/agent_spawner.py` — AgentSpawnerProvider with spawn/wait/get/list tools
- `backend/tests/smoke/test_v2_phase_1.py` — Smoke tests

### Modified Files
- `backend/src/agent_platform/db/sqlite_agent_repo.py` — `list_children()` method
- `backend/src/agent_platform/api/main.py` — register AgentSpawnerProvider
- `backend/src/agent_platform/api/routes.py` — GET /agents/{id}/children endpoint
- `backend/src/agent_platform/core/runtime.py` — inject agent_id into spawner tool calls

## Risks & Decisions
- **Synchronous spawn (spawn_agent runs child inline):** The parent's tool call blocks until the child completes. This is the simplest model for V2 Phase 1. Async/parallel spawn is V2 Phase 3 (orchestration patterns).
- **Child inherits parent's config:** Unless overridden in the spawn call. System prompt can be customized per child.
- **No special memory isolation:** Existing PUBLIC/PRIVATE visibility model handles cross-agent memory. Children can read parent's PUBLIC memories via `include_public=True` (already the default).
- **AgentSpawnerProvider needs runtime reference:** The spawner creates and runs child agents, so it needs access to the same dependencies as the runtime. We pass individual deps rather than circular runtime reference.
