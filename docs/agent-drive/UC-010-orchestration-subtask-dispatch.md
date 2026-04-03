# UC-010: Orchestration Subtask Dispatch (Tool & Agent Execution)

## Purpose

Validate that orchestrated subtasks can execute via three dispatch modes: direct LLM calls (default), registered tools (filesystem/shell), and spawned sub-agents — all within a single orchestrated plan. Validates V2 Phase 6 deliverables.

## Preconditions

- Backend running at `http://localhost:8000`
- MCP servers configured (filesystem + shell) in `lyra.config.json`
- Work directory exists: `/home/radek/Code/lyra-seed/work/test/`
- No specific DB state required

## Steps

### Step 1: Create orchestrator agent

```
POST /agents
{"name": "dispatch-tester"}
```

Record the agent ID.

### Step 2: Verify tool availability

```
GET /tools
```

**Expected:** `shell_execute` and filesystem tools (e.g., `fast_write_file`) are available. These are the tools that orchestration subtasks can be assigned to.

### Step 3: Orchestrate with mixed subtask types (LLM + tool)

```
POST /agents/{id}/prompt
{"message": "Orchestrate this task: First, write a brief description of what Python is (use your own knowledge). Then use the shell_execute tool to run 'date' and report the current date. Use sequential strategy."}
```

**Expected:**
- Decomposer creates a plan with at least 2 subtasks
- The first subtask should have `assigned_to: "llm"` or `"spawn_agent"` (knowledge task)
- The second subtask should have `assigned_to: "shell_execute"` (tool task)
- The tool subtask uses LLM to extract arguments from the description, then calls `shell_execute`
- Events show orchestration events with `assigned_to` in payloads
- Final synthesis combines both results

### Step 4: Verify tool subtask execution in events

```
GET /agents/{id}/events
```

**Expected:**
- `orchestration.strategy` events show `assigned_to` field for each subtask
- Tool subtask shows `assigned_to: "shell_execute"` (or similar tool name)
- The tool was actually called (look for the tool result in the subtask output)
- LLM subtask shows `assigned_to: "llm"` or `"spawn_agent"`

### Step 5: Orchestrate with agent-spawned subtasks

```
POST /agents/{id}/prompt
{"message": "Orchestrate this task with parallel strategy: Spawn three sub-agents — one to list advantages of Python, one to list advantages of Go, one to list advantages of Rust. Each sub-agent should work independently."}
```

**Expected:**
- Decomposer creates 3 subtasks with `assigned_to: "spawn_agent"`
- Parallel strategy spawns 3 child agents concurrently
- Each child runs a full agent loop (with tools, memory, conversation)
- Parent waits for all children to complete
- Results synthesized into a comparison
- `GET /agents/{id}/children` shows 3 new child agents
- Children have status `idle` or `completed` after orchestration finishes

### Step 6: Verify agent subtask events and children

```
GET /agents/{id}/events
GET /agents/{id}/children
```

**Expected:**
- `AGENT_SPAWN` events for each spawned subtask child
- `AGENT_COMPLETE` events when children finish
- `orchestration.strategy` events show `assigned_to: "spawn_agent"`
- Children list shows 3+ agents with the parent's ID
- Each child has conversation history (they ran a full runtime loop)

### Step 7: Orchestrate with mixed types (LLM + tool + agent)

```
POST /agents/{id}/prompt
{"message": "Orchestrate this task sequentially: 1) Use shell_execute to run 'uname -s' and get the OS name. 2) Based on the OS name, write a brief paragraph about that operating system's history. 3) Spawn a sub-agent to review the paragraph for accuracy and suggest improvements."}
```

**Expected:**
- Plan has 3 subtasks of different types:
  - Subtask 1: `assigned_to: "shell_execute"` (tool)
  - Subtask 2: `assigned_to: "llm"` (knowledge, may receive OS name from previous stage)
  - Subtask 3: `assigned_to: "spawn_agent"` (review agent)
- Sequential execution respects order
- Pipeline-like context: each step can reference results from previous steps
- Final synthesis combines tool output + LLM analysis + agent review

### Step 8: Test backward compatibility — pure LLM orchestration

```
POST /agents/{id}/prompt
{"message": "Orchestrate this: Compare REST vs GraphQL vs gRPC for API design. Use parallel strategy."}
```

**Expected:**
- All subtasks get `assigned_to: "llm"` or `"spawn_agent"` (no tool use needed)
- Orchestration works exactly as before V2P6 — no behavioral change for pure-knowledge tasks
- Results synthesized into a coherent comparison

### Step 9: Test failure handling with tool subtask

```
POST /agents/{id}/prompt
{"message": "Orchestrate this: Use shell_execute to run 'nonexistent_command_xyz' (this will fail). Then write a summary of the results. The first task should be skippable if it fails."}
```

**Expected:**
- Tool subtask fails (command not found or not in allowlist)
- If decomposer sets `failure_policy: "skip"`, the subtask is skipped and orchestration continues
- If decomposer sets `failure_policy: "escalate"`, orchestration fails gracefully with error context
- Either way, the failure is handled — no crash, no hang

### Step 10: Collect observability data

```
GET /agents/{id}/events
GET /agents/{id}/children
GET /agents/{id}/cost
```

## Success criteria

1. LLM subtasks execute via direct LLM call (backward compatible, no behavior change)
2. Tool subtasks call registered tools via the registry with LLM-extracted arguments
3. Agent subtasks spawn child agents, wait for results, and extract responses
4. Mixed plans (LLM + tool + agent) work in sequential strategy
5. Parallel strategy runs mixed subtask types concurrently
6. Pipeline context passes between subtask types (tool output → LLM input → agent input)
7. Spawned subtask agents appear in `/children` with correct parent linkage
8. Failure policies (skip, escalate, retry) work for tool and agent subtasks
9. Events include `assigned_to` field showing dispatch mode per subtask
10. Backward compatibility: pure-LLM orchestrations work identically to pre-V2P6

## What to report

- Decomposed plan for each orchestration: subtask descriptions, assigned_to values, strategy
- Per subtask: dispatch mode (LLM/tool/agent), execution result (summarized), duration
- Tool subtasks: which tool was called, what arguments were extracted, tool result
- Agent subtasks: child agent IDs, child conversation length, child result
- Mixed plan: verify different dispatch modes in same plan
- Event timeline: orchestration events with assigned_to payloads
- Children created: count, parent linkage, status after orchestration
- Failure handling: what happened on tool/agent failure
- Cost breakdown: compare cost of tool/agent subtasks vs LLM-only orchestrations
- Backward compatibility: pure-LLM orchestration unchanged
- Any unexpected behavior: wrong dispatch mode, missing context, failed arg extraction
