# UC-009: Graph View & Observation UI Showcase

## Purpose

Validate the V2 Phase 5 graph view end-to-end: agent network visualization, orchestration subtask rendering, inter-agent message edges, dashboard stats, agent spawning from UI, real-time SSE updates, and filters. Also verify existing observation UI pages remain unchanged.

## Preconditions

- Backend running at `http://localhost:8000`
- Frontend running at `http://localhost:3000`
- MCP servers configured (filesystem + shell)
- Clean or existing DB (test creates its own agents)

## Steps

### Step 1: Verify navigation

Open `http://localhost:3000`.

**Expected:**
- Header nav shows three links: AGENTS, MEMORIES, GRAPH
- Click GRAPH — navigates to `/graph`
- Click AGENTS — navigates back to `/`
- Click MEMORIES — navigates to `/memories`
- All three pages load without errors

### Step 2: Empty graph state

Navigate to `/graph` with no agents (or a clean DB).

**Expected:**
- DashboardHeader shows `AGENTS: 0`
- Graph canvas is empty (React Flow renders with background grid)
- Sidebar shows Filters section and Spawn Agent form
- Connection status shows LIVE (green) if SSE is connected

### Step 3: Spawn agent from graph view

In the Spawn Agent form on the sidebar:
1. Enter name: `graph-test-1`
2. Leave model empty (uses default)
3. Click CREATE

**Expected:**
- Agent node appears on the graph canvas
- Node shows: name `graph-test-1`, status `idle` (gray border), model name
- DashboardHeader updates to `AGENTS: 1`, shows `1 idle`
- Node is positioned automatically by dagre layout

### Step 4: Spawn a second agent

Spawn another agent named `graph-test-2`.

**Expected:**
- Second node appears on the graph
- Both nodes visible, auto-positioned (side by side or stacked)
- DashboardHeader shows `AGENTS: 2`
- Nodes are separate (no parent-child edge, both are root agents)

### Step 5: Click node to drill into agent detail

Click the `graph-test-1` node on the graph.

**Expected:**
- Navigates to `/agents/{graph-test-1-id}` — the existing agent detail page
- Agent detail page loads correctly with conversation panel, event timeline
- Click browser back or GRAPH nav link to return to `/graph`
- Graph state is preserved (both nodes still visible)

### Step 6: Trigger agent activity and observe real-time updates

In a separate tab/window, send a prompt to `graph-test-1`:
```
POST /agents/{graph-test-1-id}/prompt
{"message": "Say hello."}
```

**Expected:**
- On the graph view, `graph-test-1` node border changes to green (#00ff41) when status becomes `running`
- Status badge on the node shows `RUNNING`
- DashboardHeader updates: `1 running, 1 idle`
- After completion, node border returns to gray (#555), status shows `IDLE`
- All updates happen in real-time via SSE (no page refresh needed)

### Step 7: Spawn sub-agent and verify parent-child edge

Send a prompt to `graph-test-1`:
```
POST /agents/{graph-test-1-id}/prompt
{"message": "Spawn a sub-agent named 'worker' using the worker template with task: 'Say ready.'"}
```

**Expected:**
- New `worker` node appears on the graph
- Solid parent-child edge connects `graph-test-1` → `worker`
- Edge is animated (dashed) while `worker` is running
- Edge becomes solid when `worker` returns to idle
- DashboardHeader count updates to 3 agents
- Dagre auto-layout repositions nodes hierarchically (parent above child)

### Step 8: Inter-agent messaging and message edges

Send a prompt to `graph-test-1`:
```
POST /agents/{graph-test-1-id}/prompt
{"message": "Send the worker a task message: 'Calculate 2+2 and report.'"}
```

**Expected:**
- Dashed message edge appears from `graph-test-1` to `worker`
- Edge is colored purple (#aa66ff) for task type
- Edge label shows `task`
- After worker replies, a second edge appears from `worker` to `graph-test-1` (green, `result` type)
- Message edges appear in real-time via SSE

### Step 9: Message type filters

In the sidebar Filters section:
1. Uncheck `result` message type
2. Observe: result edges disappear, task edges remain
3. Uncheck `task` type
4. Observe: all message edges disappear
5. Re-check both

**Expected:**
- Edges show/hide immediately as checkboxes toggle
- Parent-child edges are NOT affected by message type filters
- "Show messages" toggle hides ALL message edges when unchecked

### Step 10: Time range filter

Set time range to `15m`.

**Expected:**
- Only messages from the last 15 minutes shown
- Switch to `All` — all messages shown
- Switch to `1h` — default range

### Step 11: Orchestrate a task and verify subtask visualization

Send a prompt to `graph-test-1`:
```
POST /agents/{graph-test-1-id}/prompt
{"message": "Orchestrate this task with parallel strategy: List pros of Python, list pros of Go, then synthesize a comparison."}
```

**Expected:**
- `graph-test-1` node expands to show subtask pills inside
- Each subtask shows description (truncated), status dot, and status label
- Subtask colors: pending=#555, running=#00ff41, completed=#6688ff
- Parallel subtasks show as running simultaneously (multiple green dots)
- After orchestration completes, all subtasks show completed (blue)
- Synthesis row appears at the bottom with "SYNTHESIS COMPLETED"
- Node height increases to accommodate subtask list

### Step 12: Subtask visibility toggle

In the sidebar, uncheck "Show subtasks".

**Expected:**
- Subtask pills disappear from all agent nodes
- Nodes shrink back to compact size (name + model + status only)
- Re-check: subtasks reappear

### Step 13: Dashboard header accuracy

After all the above activity, verify the dashboard header shows accurate counts.

**Expected:**
- Total agent count matches reality (3: graph-test-1, graph-test-2, worker)
- Status breakdown is correct (e.g., `2 idle, 1 completed` or similar)
- If any agent is `waiting_hitl`, an orange "PENDING HITL" badge appears

### Step 14: Connection control

Click the LIVE button in the sidebar footer.

**Expected:**
- Button changes to OFFLINE (gray)
- SSE disconnects — no more real-time updates
- Click OFFLINE — reconnects, button shows LIVE (green)
- Pending updates appear after reconnection

### Step 15: Existing pages unchanged

Navigate to each existing page and verify no regressions:

1. `/` (Agents page) — agent list with create form, costs, delete buttons
2. `/agents/{id}` (Agent detail) — conversation panel, event timeline, HITL panel, sub-agents bar, message panel
3. `/memories` (Memory browser) — search, type filter, archive/delete

**Expected:**
- All existing pages render correctly
- No visual changes, no broken functionality
- Existing UI is completely independent of the new graph view

## Success criteria

1. GRAPH nav link present in header, navigates to `/graph`
2. Graph canvas renders with React Flow (background grid, zoom/pan, minimap)
3. Agent nodes show name, model, status with correct colors
4. Parent-child edges appear when sub-agents are spawned
5. Message edges appear with type-based coloring and labels
6. Orchestration subtasks render inside agent nodes with status colors
7. Dashboard header shows accurate agent counts and status breakdown
8. Spawn agent form creates root agents that appear on the graph
9. All filters work: message type checkboxes, time range, show/hide toggles
10. Real-time SSE updates: status changes, new agents, messages appear live
11. Click node navigates to existing agent detail page
12. Connection control (LIVE/OFFLINE) toggles SSE
13. Existing pages (`/`, `/agents/[id]`, `/memories`) unchanged

## What to report

- Screenshot or description of graph with agents, edges, and subtasks
- Node appearance: colors match spec for each status
- Edge types observed: parent-child (solid), message (dashed + colored)
- Subtask rendering: count, status colors, synthesis indicator
- Dashboard stats accuracy
- Filter behavior: which toggles work, any missing functionality
- Real-time update latency: how quickly do SSE events reflect on the graph
- Spawn form: agent creation success, node appearance timing
- Navigation: click-to-drill works, back navigation preserves state
- Any layout issues: overlapping nodes, edges crossing through nodes, minimap accuracy
- Existing page verification: any regressions observed
- Browser console errors (if any)
