# UC-002: HITL Approval Flow

## Purpose

Verify that an agent with `hitl_policy: "always_ask"` pauses execution at tool calls, waits for human approval, and resumes correctly after approval. Tests the full HITL gate lifecycle.

## Preconditions

- Backend running at `http://localhost:8000`
- No specific DB state required (works with clean or existing DB)

## Technical note

The `POST /agents/{id}/prompt` endpoint blocks until the agent completes its full runtime loop. When a HITL gate is hit, the agent pauses and the prompt call hangs. To handle this:

1. Send the prompt in a background process
2. Poll `GET /agents/{id}` until status is `waiting_hitl`
3. Send approval via `POST /agents/{id}/hitl-respond`
4. Repeat poll/approve if the agent hits another HITL gate
5. Collect the result when the background process completes

## Steps

### Step 1: Create agent with HITL enabled

```
POST /agents
{"name": "hitl-test", "config": {"hitl_policy": "always_ask"}}
```

Record the agent ID. Verify `hitl_policy` is `always_ask`.

### Step 2: Send prompt that triggers a tool call (background)

```bash
curl -s -X POST "http://localhost:8000/agents/{id}/prompt" \
  -H 'Content-Type: application/json' \
  -d '{"message": "Please recall what you know about me."}' \
  > /tmp/hitl-result.json 2>&1 &
```

This should trigger the agent to call `recall`, which will hit the HITL gate.

### Step 3: Poll for HITL gate

```bash
# Poll every 1 second, up to 20 attempts
STATUS=$(curl -s "http://localhost:8000/agents/{id}" | jq -r '.status')
# Wait until status == "waiting_hitl"
```

**Expected:** Status transitions from `idle` → `running` → `waiting_hitl` within ~5 seconds.

### Step 4: Approve the tool call

```
POST /agents/{id}/hitl-respond
{"approved": true, "message": "Go ahead"}
```

**Expected:** Returns `{"status": "ok"}`. Agent resumes execution.

### Step 5: Collect result

Wait for the background prompt to complete, then read the result.

**Expected:** Agent completes the `recall` tool call and returns a response with recalled memories.

### Step 6: Verify events

```
GET /agents/{id}/events
```

**Expected events in order:**
1. `memory_read` — memory injection
2. `llm_request` / `llm_response` — agent decides to call recall
3. `hitl_request` — HITL gate emitted with pending tool call details
4. `hitl_response` — approval received
5. `tool_call: recall` — tool executes after approval
6. `tool_result: recall` — results returned
7. `llm_request` / `llm_response` — agent synthesizes final answer

### Step 7: (Optional) Test denial

Create another agent, send a prompt, but deny the tool call:

```
POST /agents/{id}/hitl-respond
{"approved": false, "message": "Not allowed"}
```

**Expected:** Agent receives the denial, does not execute the tool, and responds explaining it couldn't complete the action.

## Success criteria

1. Agent status transitions correctly: idle → running → waiting_hitl → running → idle
2. HITL gate blocks execution until approval is received
3. After approval, tool executes and agent completes normally
4. HITL_REQUEST and HITL_RESPONSE events emitted with correct payloads
5. (If denial tested) Agent handles denial gracefully without error

## What to report

- Status transition timeline with timestamps
- Time spent in `waiting_hitl` state
- HITL event payloads (what tool was gated, what the approval/denial contained)
- Agent response after approval
- Whether multiple HITL gates were hit (if the agent made multiple tool calls)
- Cost breakdown
- Any unexpected behavior (e.g., timeout, stuck state)
