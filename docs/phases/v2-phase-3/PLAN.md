# V2 Phase 3 — Plan

## Phase Reference
- **Version:** V2
- **Phase:** 3
- **Title:** Orchestration Patterns
- **Roadmap Section:** §567-584

## Prerequisites
- [x] V2 Phase 2: Inter-Agent Communication & Async Lifecycle — COMPLETE

## Deliverables Checklist
- [ ] 3.1: Orchestration data models (SubTask, TaskPlan, OrchestrationStrategy enum, FailurePolicy)
- [ ] 3.2: Task decomposition tool (`decompose_task`) — LLM breaks complex task into subtasks
- [ ] 3.3: Orchestration strategies (Sequential, Parallel, Pipeline)
- [ ] 3.4: Result synthesis — LLM combines sub-agent results into unified response
- [ ] 3.5: Failure handling (retry, reassign, escalate, skip) — configurable per subtask
- [ ] 3.6: `orchestrate` tool — end-to-end: decompose → execute → synthesize
- [ ] 3.7: Orchestration events for observability

## Implementation Steps

### 1. Orchestration Models
**Files:** `backend/src/agent_platform/orchestration/models.py`

Define Pydantic models:
- `SubTask` — id, description, assigned_to (tool | agent), dependencies (list of subtask IDs), status, result, failure_policy
- `TaskPlan` — id, original_task, subtasks list, strategy (sequential | parallel | pipeline), status
- `SubTaskStatus` enum — PENDING, RUNNING, COMPLETED, FAILED, SKIPPED
- `OrchestrationStrategyType` enum — SEQUENTIAL, PARALLEL, PIPELINE
- `FailurePolicy` enum — RETRY, REASSIGN, ESCALATE, SKIP
- `OrchestrationResult` — plan_id, results dict, synthesized_response, status

### 2. Task Decomposition
**Files:** `backend/src/agent_platform/orchestration/decomposer.py`

- `TaskDecomposer` class:
  - `async decompose(task: str, available_tools: list[Tool], llm: LLMProvider) -> TaskPlan`
  - Uses LLM to break task into subtasks with JSON output
  - Maps each subtask to a tool call or sub-agent spawn
  - Determines dependencies between subtasks
  - Selects orchestration strategy based on dependency structure

### 3. Orchestration Strategies
**Files:** `backend/src/agent_platform/orchestration/strategies.py`

Three strategy classes implementing the existing `Strategy` protocol:
- `SequentialOrchestration` — runs subtasks one by one in order
- `ParallelOrchestration` — runs independent subtasks concurrently via asyncio.gather
- `PipelineOrchestration` — output of subtask N becomes input context for subtask N+1

Each strategy:
- Takes a TaskPlan + execution context (tool registry, agent spawner, LLM provider)
- Executes subtasks by either calling tools or spawning sub-agents
- Updates subtask statuses as they execute
- Applies failure policies on errors
- Emits events for each subtask start/complete/fail

### 4. Result Synthesis
**Files:** `backend/src/agent_platform/orchestration/synthesizer.py`

- `ResultSynthesizer` class:
  - `async synthesize(original_task: str, results: dict[str, str], llm: LLMProvider) -> str`
  - Collects all subtask results
  - Uses LLM to produce a unified response addressing the original task

### 5. Failure Handling
**Integrated into strategies.py**

Per-subtask failure policies:
- `RETRY` — retry the subtask up to N times (default 2)
- `REASSIGN` — spawn a fresh sub-agent for the failed subtask
- `ESCALATE` — stop orchestration, return error with context
- `SKIP` — mark subtask as SKIPPED, continue with remaining

### 6. Orchestration Tool Provider
**Files:** `backend/src/agent_platform/orchestration/tool_provider.py`

- `OrchestrationToolProvider` implementing `ToolProvider`:
  - `decompose_task` tool — decompose a complex task into a plan
  - `orchestrate` tool — end-to-end: decompose + execute + synthesize
- Register in main.py alongside existing providers

### 7. Event Integration
- New event payloads for orchestration events using existing EventType.TOOL_CALL/TOOL_RESULT
- Subtask-level events emitted through the event bus
- Plan creation, subtask execution, and synthesis all emit events

### 8. Wire into Application
**Files:** `backend/src/agent_platform/api/main.py`

- Create OrchestrationToolProvider in create_app
- Register with ToolRegistry
- Pass required dependencies (LLM, tool registry, agent spawner, event bus)

## Dependencies & Libraries
- No new external dependencies required
- Uses existing: Pydantic, asyncio, FastAPI, SQLite repos

## File Manifest
- `backend/src/agent_platform/orchestration/__init__.py` — already exists (empty)
- `backend/src/agent_platform/orchestration/models.py` — new: orchestration data models
- `backend/src/agent_platform/orchestration/decomposer.py` — new: task decomposition
- `backend/src/agent_platform/orchestration/strategies.py` — new: sequential/parallel/pipeline
- `backend/src/agent_platform/orchestration/synthesizer.py` — new: result synthesis
- `backend/src/agent_platform/orchestration/tool_provider.py` — new: orchestration tools
- `backend/src/agent_platform/api/main.py` — modified: wire orchestration provider
- `backend/tests/smoke/test_v2_phase_3.py` — new: smoke tests

## Risks & Decisions
- Task decomposition quality depends heavily on the LLM prompt — will need careful prompt engineering
- Parallel orchestration must handle partial failures gracefully
- Pipeline strategy must define clear input/output contract between stages
- Sub-agent spawning in strategies reuses existing AgentSpawnerProvider internals
