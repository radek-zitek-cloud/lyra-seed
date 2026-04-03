# V2 Phase 6: Smoke Tests

## Test Environment

- **Framework:** pytest with async support
- **File:** `backend/tests/smoke/test_v2_phase_6.py`
- **Mocking:** LLM calls mocked, tool calls mocked, agent spawner mocked
- **Markers:** `@pytest.mark.smoke`, `@pytest.mark.phase("v2-phase-6")`

## Tests

### ST-V2-6.1: Subtask with assigned_to "llm" uses direct LLM call (backward compat)
- **Validates:** Fallback behavior unchanged
- **Method:** Create subtask with `assigned_to="llm"`, execute via `_execute_subtask()`
- **Checks:** LLM provider called, tool registry NOT called, result returned

### ST-V2-6.2: Subtask with assigned_to matching a tool name calls the tool
- **Validates:** Tool dispatch
- **Method:** Create subtask with `assigned_to="shell_execute"`, mock tool registry with that tool
- **Checks:** `tool_registry.call_tool("shell_execute", ...)` called, tool result used as subtask output

### ST-V2-6.3: Subtask with assigned_to "spawn_agent" spawns and waits for child
- **Validates:** Agent dispatch
- **Method:** Create subtask with `assigned_to="spawn_agent"`, mock agent spawner
- **Checks:** Agent spawned with subtask description as task, wait called, child result extracted

### ST-V2-6.4: Unknown assigned_to falls back to LLM
- **Validates:** Graceful fallback
- **Method:** Create subtask with `assigned_to="nonexistent_thing"`
- **Checks:** LLM provider called (not tool registry), subtask completes successfully

### ST-V2-6.5: Sequential strategy with mixed subtask types
- **Validates:** Mixed execution in sequential mode
- **Method:** Plan with 3 subtasks: LLM, tool, agent — run sequentially
- **Checks:** Each subtask dispatched correctly by type, results collected in order

### ST-V2-6.6: Parallel strategy with mixed subtask types
- **Validates:** Concurrent mixed execution
- **Method:** Plan with 3 independent subtasks of different types — run in parallel
- **Checks:** All three run (via asyncio.gather), results collected

### ST-V2-6.7: Pipeline strategy passes context across types
- **Validates:** Output chaining across execution modes
- **Method:** Pipeline: LLM subtask → tool subtask → agent subtask, each receiving previous output
- **Checks:** Each subtask receives previous output as context

### ST-V2-6.8: Failure policy retry works for tool subtask
- **Validates:** Retry on tool failure
- **Method:** Tool subtask that fails on first call, succeeds on second
- **Checks:** Retry triggered, subtask completes on second attempt

### ST-V2-6.9: Failure policy skip works for agent subtask
- **Validates:** Skip on agent failure
- **Method:** Agent subtask that fails, with `failure_policy=SKIP`
- **Checks:** Subtask marked SKIPPED, orchestration continues

### ST-V2-6.10: Tool argument extraction from description
- **Validates:** LLM extracts structured args from natural language
- **Method:** Tool subtask with description "List files in /home", tool expects `{"path": "/home"}`
- **Checks:** LLM called to extract args, tool called with extracted args

### ST-V2-6.11: Agent subtask inherits parent config
- **Validates:** Config inheritance for spawned children
- **Method:** Parent agent has specific model and tool scoping, spawns agent subtask
- **Checks:** Child created with parent's model and allowed_tools
