# V2 Phase 6: Orchestration Subtasks with Tool & Agent Execution

## Overview

Currently all orchestration subtasks execute as standalone LLM calls regardless of the `assigned_to` field. This phase makes `assigned_to` functional: subtasks assigned to `"spawn_agent"` spawn actual child agents, subtasks assigned to a tool name call that tool via the registry, and everything else falls back to LLM calls.

Promoted from BL-005. Prerequisite for V3's capability acquisition loop.

## Prerequisites

- V2 Phase 5 complete (all prior tests passing)
- No new dependencies needed

## Architecture

The change is isolated to one function: `_execute_subtask()` in `strategies.py`. Everything else is already wired:

- `SubTask.assigned_to` field exists and is populated by the decomposer
- `tool_registry` is already passed through strategy kwargs but unused
- `AgentSpawnerProvider` already has `_spawn_agent()` and `_wait_for_agent()`
- Decomposition prompt already instructs the LLM to set `assigned_to`

### Execution dispatch (new logic in `_execute_subtask`)

```
subtask.assigned_to == "spawn_agent"
  → spawn child agent with subtask.description as task
  → wait for completion (with timeout)
  → extract last assistant message as result

subtask.assigned_to matches a registered tool name
  → call tool_registry.call_tool(name, arguments)
  → use tool result output as subtask result

subtask.assigned_to == "llm" or unrecognized
  → current behavior (direct LLM call)
```

### Key design decisions

1. **Agent subtasks use spawn + wait pattern** — the orchestration spawns a child agent and blocks until it completes. This is synchronous from the orchestration's perspective but the child runs its full async runtime loop internally (tools, memory, multi-iteration).

2. **Tool subtasks use an LLM pre-call** to extract tool arguments from the subtask description, since `call_tool()` needs structured arguments but subtask descriptions are natural language. The LLM generates a JSON arguments object, then the tool is called.

3. **Parallel strategy** handles mixed types naturally — `asyncio.gather` already runs subtasks concurrently. Agent spawns are async internally, tool calls are fast, LLM calls are fast.

4. **Pipeline context** passes previous output regardless of subtask type — agent subtasks receive it in the task prompt, tool subtasks receive it in the LLM argument extraction prompt, LLM subtasks receive it as before.

5. **Concurrency guard** — max 5 parallel agent spawns (configurable) to prevent resource exhaustion.

6. **Failure policies unchanged** — retry/reassign/skip/escalate work for all three modes. Retry re-executes the same dispatch. Reassign does the same (no different agent type to reassign to).

## File Manifest

### Modified files
```
backend/src/agent_platform/orchestration/strategies.py
  — _execute_subtask(): add dispatch branching on assigned_to
  — Pass tool_registry and agent spawner through strategy kwargs

backend/src/agent_platform/orchestration/tool_provider.py
  — Pass agent_spawner to strategy kwargs (for spawn_agent subtasks)
```

### New files
```
backend/tests/smoke/test_v2_phase_6.py  — Smoke tests
docs/phases/v2-phase-6/PLAN.md         — This file
docs/phases/v2-phase-6/SMOKE_TESTS.md  — Test specifications
docs/phases/v2-phase-6/STATUS.md       — Progress tracking
```

### Unchanged
- `orchestration/models.py` — SubTask model already has `assigned_to`
- `orchestration/decomposer.py` — already populates `assigned_to` from LLM
- `prompts/system/decompose_task.md` — already instructs LLM on `assigned_to`
- `tools/agent_spawner.py` — spawn/wait already work
- `tools/registry.py` — call_tool already works

## Implementation Steps

1. **Modify `_execute_subtask()`** in `strategies.py`:
   - Add `tool_registry` and `agent_spawner` parameters
   - Branch on `subtask.assigned_to`:
     - `"spawn_agent"`: create child agent, run it, wait, extract result
     - Tool name (check against registry): call tool with LLM-extracted args
     - Default: existing LLM call behavior
   - Update event payloads to include execution mode

2. **Update strategy classes** to pass `tool_registry` and `agent_spawner` from kwargs to `_execute_subtask()`

3. **Update `OrchestrationToolProvider._orchestrate()`** to include `agent_spawner` reference in strategy kwargs

4. **Add concurrency semaphore** for agent spawns in parallel strategy

5. **Write smoke tests** covering:
   - Tool-assigned subtask execution
   - Agent-assigned subtask execution
   - Mixed plan (LLM + tool + agent)
   - Fallback for unknown assigned_to
   - Failure policy with non-LLM subtasks

## Risks

1. **Agent subtask timeout** — child agents can take 30-60s. The orchestration timeout must accommodate this. Use the existing `wait_for_agent` timeout (300s default).

2. **Tool argument extraction** — natural language description → structured tool arguments requires an LLM call. This adds one extra LLM call per tool subtask. Use the cheaper orchestration_model for this.

3. **Spawn depth** — orchestration spawning agents that themselves orchestrate could hit the 3-level spawn depth limit. This is acceptable — depth limit is a safety guard.
