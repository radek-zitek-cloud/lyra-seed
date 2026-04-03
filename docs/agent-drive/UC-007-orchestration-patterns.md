# UC-007: Orchestration Patterns

## Purpose

Validate the full orchestration system: task decomposition, all three execution strategies (sequential, parallel, pipeline), result synthesis, autonomous tool selection, and the `orchestrationModel` config. Validates V2 Phase 3 deliverables.

## Preconditions

- Backend running at `http://localhost:8000`
- `lyra.config.json` has `orchestrationModel` set (e.g., `openai/gpt-5.4-mini`)
- Recommend clean DB or new agents to avoid cross-agent memory noise

## Steps

### Step 1: Create agent and verify config

```
POST /agents
{"name": "orchestrator"}
```

**Verify:**
- `orchestration_model` is set (from platform config or default.json)
- `max_subtasks` is set (default 10)
- `auto_extract` is true

### Step 2: Test decompose_task (plan only, no execution)

```
POST /agents/{id}/prompt
{"message": "Use decompose_task to break down this task: Design a company offsite event including venue selection, activity planning, catering, travel logistics, and budget estimation."}
```

**Expected:**
- Agent calls `decompose_task` tool
- Returns a plan with 4-5 subtasks (not more than `max_subtasks`)
- Each subtask has: description, assigned_to, failure_policy
- Strategy selected (likely `parallel` since topics are independent)
- No synthesis subtask in the plan (decomposer prompt prohibits it)
- No execution occurs — plan only

**Verify in events:**
- `tool_call` for `decompose_task`
- `tool_result` from `orchestration.decompose` with plan details
- Decomposition LLM call uses `orchestration_model` (not the agent's main model)

### Step 3: Test parallel orchestration

```
POST /agents/{id}/prompt
{"message": "Compare the programming languages TypeScript, Kotlin, and Swift. For each, cover type system strengths, ecosystem maturity, and ideal use cases."}
```

**Expected:**
- Agent autonomously chooses `orchestrate` (complex, multi-part, no tools mentioned)
- Decomposer produces 3 subtasks (one per language), parallel strategy
- All subtasks start at the same timestamp (concurrent execution)
- No synthesis subtask in the plan
- Platform's ResultSynthesizer combines results after all subtasks complete
- Response is a unified comparison document

**Verify in events:**
- `tool_call` for `orchestrate` in `core.runtime`
- `tool_call` in `orchestration.orchestrate` (plan creation)
- Multiple `tool_call`/`tool_result` in `orchestration.strategy` at same timestamp
- `tool_result` in `orchestration.orchestrate` with status `completed`
- All orchestration LLM calls use `orchestration_model`

### Step 4: Test pipeline orchestration

```
POST /agents/{id}/prompt
{"message": "Orchestrate with pipeline strategy: Step 1 - brainstorm 5 startup ideas in the developer tools space. Step 2 - evaluate each idea for market viability and pick the best one. Step 3 - write a one-paragraph elevator pitch for the winner."}
```

**Expected:**
- Agent calls `orchestrate` with `strategy: "pipeline"`
- 3 subtasks execute sequentially
- Step 2 receives Step 1's output as context (verify in event payloads)
- Step 3 receives Step 2's output as context
- Final response is a coherent elevator pitch that traces through the pipeline

**Verify in events:**
- Subtask `tool_call` events have sequential timestamps (not concurrent)
- Each subtask result builds on the previous

### Step 5: Test sequential orchestration

```
POST /agents/{id}/prompt
{"message": "Orchestrate with sequential strategy: First, define what a microservice architecture is. Second, list 5 common anti-patterns. Third, for each anti-pattern suggest a mitigation strategy."}
```

**Expected:**
- Agent calls `orchestrate` with `strategy: "sequential"`
- 3 subtasks execute one after another
- Each subtask is self-contained (unlike pipeline, no context passing)
- Results synthesized into a unified document

**Verify in events:**
- Subtask `tool_call` events have sequential timestamps
- Each subtask starts after the previous completes

### Step 6: Test autonomous strategy selection

```
POST /agents/{id}/prompt
{"message": "I need a security audit checklist covering authentication, authorization, data encryption, API security, and logging. Each topic should be covered independently and thoroughly."}
```

No tool or strategy mentioned. The agent should:
- Decide to use `orchestrate` (5 independent topics = good orchestration candidate)
- The decomposer should choose `parallel` (independent topics)

**Verify:**
- Agent chose `orchestrate` autonomously
- Decomposer selected `parallel` strategy
- 5 subtasks (one per security topic)
- No synthesis subtask in the plan

### Step 7: Verify orchestrationModel config

Query all events and check which model was used for orchestration LLM calls vs agent reasoning calls.

```
GET /agents/{id}/events
```

**Expected model usage:**
- Agent reasoning (decision to call tools, presenting results): agent's main model (e.g., gpt-5.4)
- Decomposition, subtask execution, synthesis: `orchestration_model` (e.g., gpt-5.4-mini)
- Fact extraction: `extraction_model` (e.g., gpt-5.4-mini)

### Step 8: Verify maxSubtasks cap

```
POST /agents/{id}/prompt
{"message": "Use decompose_task to plan a complete wedding: venue, catering, flowers, photography, music, invitations, dress, rings, honeymoon, transportation, accommodation, seating chart, vows, rehearsal dinner, wedding cake, favors, decorations, officiant, hair and makeup, registry."}
```

**Expected:** Plan has at most `max_subtasks` subtasks (default 10), even though 20 items were listed.

### Step 9: Collect cost data

```
GET /agents/{id}/cost
```

**Compare:**
- Cost of orchestration LLM calls (should use cheaper model)
- Cost of agent reasoning calls (main model)
- Total per-turn cost for orchestrated vs non-orchestrated turns

## Success criteria

1. `decompose_task` returns a valid plan without executing
2. Parallel strategy executes subtasks concurrently (same-second timestamps)
3. Pipeline strategy chains output to input (Step N+1 receives Step N's output)
4. Sequential strategy executes in order (sequential timestamps)
5. Agent autonomously selects `orchestrate` for complex multi-part tasks
6. Decomposer does not include a synthesis subtask
7. `orchestrationModel` is used for all orchestration LLM calls
8. `maxSubtasks` cap is enforced
9. ResultSynthesizer produces a coherent unified response
10. All orchestration events emitted with correct modules and payloads

## What to report

- For each step: tool called, strategy chosen, subtask count, execution timestamps
- Model usage breakdown: which model for which calls
- Whether synthesis subtask appeared in any plan (should not)
- Pipeline context chaining: evidence that later steps received earlier output
- maxSubtasks enforcement: actual count vs cap
- Cost breakdown by model and by turn
- Any unexpected behavior, failures, or quality issues in synthesized output
