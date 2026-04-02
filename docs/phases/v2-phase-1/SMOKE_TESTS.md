# V2 Phase 1 — Smoke Tests

## Test Environment
- Prerequisites: phases 0–7 complete, backend dependencies installed
- Platform: must pass on both Linux (bash) and Windows (PowerShell)
- LLM calls: always mocked
- External APIs: never called

## Backend Smoke Tests

### ST-V2-1.1: spawn_agent tool schema
- **Validates:** `AgentSpawnerProvider` lists the spawn_agent tool with correct schema
- **Method:** Create provider, call `list_tools()`
- **Checks:**
  - Tool named `spawn_agent` exists
  - Schema has required `name` and `task` parameters
  - Optional parameters include `system_prompt`, `model`

### ST-V2-1.2: spawn_agent creates child
- **Validates:** Calling spawn_agent creates a child agent linked to parent
- **Method:** Create parent agent, call spawn_agent tool with mocked LLM
- **Checks:**
  - Child agent created in repo with `parent_agent_id` = parent's ID
  - Tool result contains child agent ID
  - Tool result is successful

### ST-V2-1.3: spawn_agent emits AGENT_SPAWN event
- **Validates:** AGENT_SPAWN event emitted when child is spawned
- **Method:** Spawn a child agent, query events
- **Checks:**
  - AGENT_SPAWN event exists for the parent agent
  - Payload contains `child_agent_id` and `child_name`

### ST-V2-1.4: spawn_agent emits AGENT_COMPLETE event
- **Validates:** AGENT_COMPLETE event emitted when child finishes
- **Method:** Spawn a child agent (mocked LLM returns immediately), query events
- **Checks:**
  - AGENT_COMPLETE event exists for the child agent
  - Payload contains `parent_agent_id`

### ST-V2-1.5: spawn_agent child failure safe
- **Validates:** Child agent failure doesn't crash the parent
- **Method:** Spawn a child with LLM that raises an error
- **Checks:**
  - spawn_agent tool returns error result (success=False)
  - Parent agent continues running (not FAILED)

### ST-V2-1.6: get_agent_result returns child response
- **Validates:** `get_agent_result` tool retrieves child's last response
- **Method:** Spawn a child, then call get_agent_result with child's ID
- **Checks:**
  - Returns child's response content
  - Returns child's current status

### ST-V2-1.7: list_child_agents returns children
- **Validates:** `list_child_agents` tool lists spawned children
- **Method:** Spawn two children, then call list_child_agents
- **Checks:**
  - Returns two child agents
  - Each has correct name and status

### ST-V2-1.8: list_children repo method
- **Validates:** `SqliteAgentRepo.list_children()` queries correctly
- **Method:** Create parent + 2 children + 1 unrelated agent, call list_children
- **Checks:**
  - Returns exactly 2 agents
  - Both have parent_agent_id = parent's ID
  - Unrelated agent not included

### ST-V2-1.9: children API endpoint
- **Validates:** `GET /agents/{id}/children` returns child agents
- **Method:** Create parent + child agents in DB, call API endpoint
- **Checks:**
  - Returns 200 with JSON array
  - Array contains the child agent(s)

### ST-V2-1.10: wait_for_agent returns result
- **Validates:** `wait_for_agent` tool returns child's result
- **Method:** Spawn a child (completes immediately with mock), call wait_for_agent
- **Checks:**
  - Returns child's response content
  - Returns successfully

### ST-V2-1.11: agent_id injection for spawner tools
- **Validates:** Runtime injects agent_id into spawner tool arguments
- **Method:** Run parent agent with mocked LLM that calls spawn_agent (without agent_id in args), verify agent_id is injected
- **Checks:**
  - spawn_agent receives parent's agent_id
  - Child is created with correct parent_agent_id

### ST-V2-1.12: child inherits parent config defaults
- **Validates:** Child agent inherits model and temperature from parent unless overridden
- **Method:** Create parent with specific model/temperature, spawn child without overrides
- **Checks:**
  - Child's config.model matches parent's
  - Child's config.temperature matches parent's
