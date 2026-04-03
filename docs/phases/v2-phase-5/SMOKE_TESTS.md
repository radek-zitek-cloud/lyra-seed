# V2 Phase 5: Smoke Tests

## Test Environment

- **Framework:** Vitest + React Testing Library
- **File:** `frontend/tests/smoke/smoke.v2-phase-5.spec.tsx`
- **Mocking:** React Flow, dagre, and fetch mocked (jsdom has no layout APIs)

## Tests

### ST-V2-5.1: GraphPage renders without crash
- **Validates:** 5.1 — page mounts with mocked data
- **Checks:** React Flow container and LIVE button present

### ST-V2-5.2: DashboardHeader shows agent counts
- **Validates:** 5.4 — dashboard stats from mock agents
- **Checks:** Total count, per-status breakdown displayed

### ST-V2-5.3: AgentNode renders name, model, status
- **Validates:** 5.1 — node displays agent info
- **Checks:** Name, model text, status badge present

### ST-V2-5.4: AgentNode shows subtasks when orchestration present
- **Validates:** 5.2 — subtask pills inside node
- **Checks:** 3 subtask rows rendered with descriptions

### ST-V2-5.5: AgentNode status colors match spec
- **Validates:** 5.1 — each status maps to correct color
- **Checks:** idle=#555, running=#00ff41, waiting_hitl=#ffaa00, completed=#6688ff, failed=#ff3333

### ST-V2-5.6: buildNodes produces correct node count
- **Validates:** 5.1 — one node per agent
- **Checks:** 3 agents → 3 nodes with correct IDs and type

### ST-V2-5.7: buildEdges produces parent-child edges
- **Validates:** 5.1 — edge for each parent-child pair
- **Checks:** 2 children → 2 parentChild edges with correct source/target

### ST-V2-5.8: buildEdges produces message edges
- **Validates:** 5.3 — edge for each message
- **Checks:** 1 message → 1 message edge with correct source/target

### ST-V2-5.9: buildEdges respects message type filter
- **Validates:** 5.3 — filtered types excluded
- **Checks:** Filter to "task" only → "result" message excluded

### ST-V2-5.10: SpawnAgentForm renders with required fields
- **Validates:** 5.4 — name input and create button
- **Checks:** Placeholder text and button present

### ST-V2-5.11: GraphFilters renders controls
- **Validates:** 5.3 — filter checkboxes and time range
- **Checks:** Show messages/subtasks checkboxes, time range buttons, message type checkboxes

### ST-V2-5.12: Subtask status colors match spec
- **Validates:** 5.2 — 5 subtask statuses map to correct colors
- **Checks:** pending=#555, running=#00ff41, completed=#6688ff, failed=#ff3333, skipped=#888

### ST-V2-5.13: Layout nav includes GRAPH link
- **Validates:** 5.1 — header navigation updated
- **Checks:** layout.tsx contains href="/graph" and "GRAPH" text
