# UC-015: Agent Loop, Config Reload & Time Awareness

## Purpose

Validate the agent loop (scheduled periodic wake-ups), live config reload, LLM response streaming, agent time awareness, and recursive knowledge ingestion. These are all post-V4 enhancements that work together to enable long-running monitored agents.

## Preconditions

- Backend running at `http://localhost:8000` (restart after merging post-V4 changes)
- Frontend running at `http://localhost:3000`
- Knowledge directory with `docs` symlink in place (`knowledge/docs -> ../docs`)
- At least one agent template in `prompts/` (default.md)

## Steps

### Part A: Agent Loop

#### Step 1: Create a test agent

```
POST /agents
{"name": "loop-tester"}
```

Record the `agent_id`.

#### Step 2: Start a loop via prompt

```
POST /agents/{id}/prompt
{"message": "Use agent_loop to start a loop with interval 15 seconds and message 'Periodic check'. Then say done."}
```

**Expected:**
- Agent calls `agent_loop(action="start", interval=15, message="Periodic check")`
- Tool result returns `{"status": "started", "interval": 15, ...}`
- Agent responds with confirmation

#### Step 3: Verify first scheduled wake-up

Wait ~16 seconds, then check events:

```
GET /agents/{id}/events
```

**Expected:**
- New `memory_read` event appears after the 15-second mark (scheduler woke the agent)
- An `llm_request` / `llm_response` cycle from the wake-up turn
- The wake prompt contains `[task from scheduler]: Periodic check`

#### Step 4: Verify second wake-up

Wait another ~15 seconds, check events again.

**Expected:**
- Another wake-up cycle appears ~15 seconds after the first
- Agent status returns to `idle` between wake-ups

#### Step 5: Verify loop status from within agent

```
POST /agents/{id}/prompt
{"message": "Check your agent_loop status."}
```

**Expected:**
- Agent calls `agent_loop(action="status")`
- Returns `{"active": true, "interval": 15, "message": "Periodic check", "next_wake": "..."}`

#### Step 6: Adjust loop interval

```
POST /agents/{id}/prompt
{"message": "Change your loop interval to 30 seconds."}
```

**Expected:**
- Agent calls `agent_loop(action="start", interval=30, message="Periodic check")`
- Next wake-up occurs ~30 seconds later (not 15)

#### Step 7: Stop the loop

```
POST /agents/{id}/prompt
{"message": "Stop your loop."}
```

**Expected:**
- Agent calls `agent_loop(action="stop")`
- Returns `{"status": "stopped"}`
- No further wake-up events appear after 30+ seconds

#### Step 8: Minimum interval guard

```
POST /agents/{id}/prompt
{"message": "Start a loop with interval 2 seconds."}
```

**Expected:**
- Agent calls `agent_loop(action="start", interval=2, ...)`
- Tool result shows `interval: 10` (clamped to minimum, not 2)

#### Step 9: Delete agent with active loop

Start a new loop first:

```
POST /agents/{id}/prompt
{"message": "Start a loop with interval 10 seconds and message 'tick'."}
```

Then delete the agent:

```
DELETE /agents/{id}
```

**Expected:**
- Delete succeeds (200, not 500)
- No scheduler errors in backend logs after deletion
- Loop is automatically unregistered

### Part B: Config Reload

#### Step 10: Create agent and verify config

```
POST /agents
{"name": "reload-tester"}
```

```
GET /agents/{id}
```

**Expected:** Agent config has current `system_prompt` from `prompts/default.md`.

#### Step 11: Prompt the agent to establish conversation

```
POST /agents/{id}/prompt
{"message": "Hello, what tools do you have?"}
```

**Expected:** Agent responds, conversation exists.

#### Step 12: Reload config

```
POST /agents/{id}/reload-config
```

**Expected:**
- Returns `{"status": "reloaded", "prompt_changed": false, "model_changed": false, "conversation_cleared": true}`
- `conversation_cleared: true` indicates the old conversation was deleted

#### Step 13: Verify conversation cleared

```
GET /agents/{id}/conversations
```

**Expected:** Empty array or no conversations (will be recreated on next prompt).

#### Step 14: Verify agent works after reload

```
POST /agents/{id}/prompt
{"message": "What time is it?"}
```

**Expected:**
- Agent starts a fresh conversation with the reloaded system prompt
- System prompt includes current date/time injection
- Agent responds normally

#### Step 15: Reload with active loop clears loop

If the agent has an active loop:

```
POST /agents/{id}/prompt
{"message": "Start a loop with interval 10 seconds."}
```

Then:

```
POST /agents/{id}/reload-config
```

**Expected:**
- Loop is unregistered (no more wake-ups)
- Agent gets a clean slate

#### Step 16: UI reload button

Open the agent in the frontend at `http://localhost:3000/agents/{id}`.

**Expected:**
- Blue "RELOAD CONFIG" button is visible in the header
- Clicking it refreshes the page and reloads the agent's config
- Config panel shows updated values

### Part C: Time Awareness

#### Step 17: System prompt time injection

Create a fresh agent:

```
POST /agents
{"name": "time-tester"}
```

```
POST /agents/{id}/prompt
{"message": "What is the current date and time?"}
```

**Expected:**
- Agent answers with the current date/time from its system prompt injection
- Does NOT need to call `get_current_time` for this (it's in the system prompt)

#### Step 18: get_current_time tool

```
POST /agents/{id}/prompt
{"message": "What time is it in Europe/Prague right now? Use the get_current_time tool."}
```

**Expected:**
- Agent calls `get_current_time(timezone="Europe/Prague")`
- Returns formatted time with CEST/CET timezone and day of week
- Time is current (not stale from system prompt)

#### Step 19: Invalid timezone handling

```
POST /agents/{id}/prompt
{"message": "What time is it in Narnia/Wardrobe?"}
```

**Expected:**
- Agent calls `get_current_time(timezone="Narnia/Wardrobe")`
- Tool returns error: `Unknown timezone: Narnia/Wardrobe`
- Agent handles gracefully and explains the timezone is invalid

### Part D: LLM Streaming

#### Step 20: Verify streaming in UI

Open the agent page in the frontend. Send a prompt that requires a long response:

```
POST /agents/{id}/prompt
{"message": "Write a detailed paragraph about the history of computing."}
```

**Expected:**
- While the LLM is generating, a streaming assistant message appears in the conversation panel with a blinking cursor
- Text appears incrementally (not all at once)
- After completion, the streaming bubble disappears and the final message replaces it
- `llm_token` events are NOT shown in the event timeline (filtered out to avoid noise)

#### Step 21: Verify streaming during tool use

```
POST /agents/{id}/prompt
{"message": "Search the knowledge base for information about Lyra's memory system, then summarize it."}
```

**Expected:**
- Streaming content appears for the final response (after tool calls complete)
- Streaming clears on each new `llm_request` event (between tool call and response)

### Part E: Recursive Knowledge Ingestion

#### Step 22: Verify recursive ingestion at startup

Check backend startup logs for knowledge base source count.

**Expected:**
- Source count includes files from subdirectories (e.g., `docs/phases/v1-phase-0/PLAN.md`)
- Source count is significantly higher than just top-level `knowledge/*.md` files
- Symlinked `knowledge/docs/` directory is followed

#### Step 23: Search for phase-specific knowledge

```
POST /agents/{id}/prompt
{"message": "Search the knowledge base for V2 Phase 3 orchestration patterns."}
```

**Expected:**
- Agent calls `search_knowledge` and finds results from `docs/phases/v2-phase-3/PLAN.md` or similar
- Results have correct relative-path source names (e.g., `docs/phases/v2-phase-3/PLAN.md`), not just `PLAN.md`

#### Step 24: No source name collisions

```
GET /knowledge/sources
```

**Expected:**
- Multiple distinct `PLAN.md` sources appear with full paths (e.g., `docs/phases/v1-phase-0/PLAN.md`, `docs/phases/v1-phase-1/PLAN.md`, etc.)
- No duplicate or overwritten sources

### Part F: UI Config Display

#### Step 25: Verify all config fields displayed

Open any agent in the frontend and expand the CONFIG panel.

**Expected fields visible:**
- Core: model, temp, max_iter, hitl, hitl_timeout, ctx_tokens, mem_k, max_subtasks, auto_extract
- Model overrides: summary_model, extraction_model, orchestration_model (if set)
- Memory GC: prune_threshold, prune_max (if set)
- Retry: retries, retry_delay, retry_timeout (if set)
- Tool access: allowed_tools (purple), allowed_mcp_servers (cyan, if set)
- Memory sharing: key:value pairs (green, if set)
- System prompt: collapsible pre block

## Success Criteria

1. Agent loop starts, wakes agent on schedule, and stops on command
2. Loop interval adjustment works (calling start again with new interval)
3. Minimum interval guard clamps to 10 seconds
4. Deleting an agent with active loop succeeds without errors
5. Config reload re-resolves from source files and clears conversation
6. Config reload unregisters active loops
7. UI RELOAD CONFIG button works
8. System prompt includes current date/time at conversation start
9. `get_current_time` tool works with timezone support
10. LLM responses stream incrementally in the UI
11. Streaming clears properly between tool calls and on completion
12. Knowledge ingestion is recursive and follows symlinks
13. No source name collisions in recursive ingestion
14. All config fields visible in UI config panel

## What to Report

- Loop wake-up timing accuracy (target vs actual interval)
- Number of wake-up cycles observed
- Config reload response (what changed)
- Time tool output with timezone
- Streaming behavior description (latency to first token, smoothness)
- Knowledge source count at startup (before and after recursive fix)
- Source names in knowledge search results (verify relative paths)
- Screenshots of UI config panel and streaming
- Any errors in backend logs
- Cost breakdown per section
