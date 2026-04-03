# UC-006: Inter-Agent Communication & Async Lifecycle

## Purpose

Deep validation of V2 Phase 2 features: message type semantics, auto-wake rules, guidance injection, stop vs dismiss lifecycle, message filtering, error handling on invalid targets, and reusable worker patterns. Goes deeper than UC-005's broad multi-agent coverage.

## Preconditions

- Backend running at `http://localhost:8000`
- MCP servers configured (filesystem + shell)
- Worker template exists in `prompts/`

## Steps

### Step 1: Create parent and spawn a reusable worker

```
POST /agents
{"name": "manager"}

POST /agents/{manager_id}/prompt
{"message": "Spawn a sub-agent named 'worker-alpha' using the worker template with task: 'You are a reusable assistant. Acknowledge you are ready and wait for further instructions.'"}
```

Wait for worker to finish initial task and go IDLE.

**Expected:**
- Worker created, runs initial task, returns to IDLE
- `AGENT_SPAWN` event on manager
- `AGENT_COMPLETE` event on worker
- `GET /agents/{manager_id}/children` shows worker-alpha as IDLE

### Step 2: Message type semantics — TASK triggers auto-wake

```
POST /agents/{manager_id}/prompt
{"message": "Send worker-alpha a task message: 'Calculate 7 * 13 and report the answer.'"}
```

Wait for worker to process (auto-wake from IDLE).

**Expected:**
- Manager calls `send_message` with `message_type: "task"`
- `MESSAGE_SENT` event on manager, `MESSAGE_RECEIVED` event on worker
- Worker auto-wakes from IDLE, processes the task
- Worker sends result back via `send_message` with `message_type: "result"`
- Worker returns to IDLE after processing
- Message consumed (no longer in inbox)

### Step 3: Message type semantics — QUESTION triggers auto-wake

```
POST /agents/{manager_id}/prompt
{"message": "Send worker-alpha a question: 'What was the result of your last calculation?'"}
```

Wait for worker to process.

**Expected:**
- Manager calls `send_message` with `message_type: "question"`
- Worker auto-wakes, processes the question
- Worker sends answer back with `message_type: "answer"` or `"result"`
- Auto-wake triggered (QUESTION is an actionable message type)

### Step 4: Message type semantics — STATUS_UPDATE does NOT auto-wake

```
POST /agents/{manager_id}/prompt
{"message": "Send worker-alpha a status_update message: 'FYI: The project deadline has been extended to May 1st.' Do NOT use task or question type — use status_update."}
```

Check worker status immediately after sending (should still be IDLE).

```
GET /agents/{worker_id}
```

**Expected:**
- Manager calls `send_message` with `message_type: "status_update"`
- `MESSAGE_SENT` event on manager
- Worker remains IDLE — status_update does NOT trigger auto-wake
- Message stays in worker's inbox (not consumed)

Verify:
```
GET /agents/{worker_id}/messages?direction=inbox
```
Should show the status_update message waiting.

### Step 5: Queued message consumed on next wake

Send a TASK to wake the worker, which should also see the queued status_update:

```
POST /agents/{manager_id}/prompt
{"message": "Send worker-alpha a task: 'Check your messages and report everything you received.'"}
```

**Expected:**
- TASK triggers auto-wake
- Worker wakes and processes the task
- Worker should also see/process the queued status_update from Step 4
- Both messages consumed after processing

### Step 6: Message direction filtering via API

```
GET /agents/{manager_id}/messages?direction=sent
GET /agents/{manager_id}/messages?direction=inbox
GET /agents/{worker_id}/messages?direction=sent
GET /agents/{worker_id}/messages?direction=inbox
GET /agents/{worker_id}/messages?direction=all
```

**Expected:**
- Manager sent: task, question, status_update, task messages
- Manager inbox: result/answer messages from worker
- Worker sent: result/answer messages to manager
- Worker inbox: should be empty (all consumed)
- Direction filtering returns correct subsets

### Step 7: Guidance injection to running agent

Spawn a second worker with a long-running task:

```
POST /agents/{manager_id}/prompt
{"message": "Spawn a sub-agent named 'writer' using the worker template with task: 'Write a detailed 500-word essay about the history of the internet. Take your time and be thorough.'"}
```

While the writer is RUNNING, send guidance:

```
POST /agents/{writer_id}/messages
{"content": "Focus specifically on the role of ARPANET and Tim Berners-Lee. Skip everything else.", "message_type": "guidance", "from_agent_id": "{manager_id}"}
```

**Expected:**
- Guidance message injected into the writer's conversation as a system message
- Writer's next LLM iteration picks up the guidance
- Writer's output reflects the guidance (focused on ARPANET/Berners-Lee)
- `MESSAGE_RECEIVED` event on writer
- Guidance message deleted after injection

### Step 8: Stop a running agent

If the writer is still running, stop it:

```
POST /agents/{manager_id}/prompt
{"message": "Stop the writer agent immediately."}
```

**Expected:**
- Manager calls `stop_agent`
- Writer transitions from RUNNING to IDLE (not COMPLETED)
- Writer is still reusable — can receive new tasks
- Background task cancelled gracefully

If writer already finished, spawn a new agent with a long task and stop it.

### Step 9: Reuse a stopped agent

```
POST /agents/{manager_id}/prompt
{"message": "Send the writer a new task: 'Write a haiku about programming.'"}
```

**Expected:**
- TASK triggers auto-wake on the stopped (IDLE) worker
- Writer processes the new task with its accumulated conversation history
- Writer returns to IDLE after completion
- Conversation history preserved from before the stop

### Step 10: Dismiss an agent (permanent)

```
POST /agents/{manager_id}/prompt
{"message": "Dismiss the writer agent — we are done with it permanently."}
```

**Expected:**
- Manager calls `dismiss_agent`
- Writer status changes to COMPLETED
- Writer is no longer reusable

### Step 11: Send message to dismissed agent (error case)

```
POST /agents/{manager_id}/prompt
{"message": "Try to send the writer a task: 'Write another haiku.' Report what happens."}
```

**Expected:**
- `send_message` fails with error: agent cannot receive messages (status COMPLETED)
- Manager reports the failure to the user
- No auto-wake occurs

### Step 12: Stop vs dismiss distinction

Verify worker-alpha is still IDLE (not dismissed):

```
POST /agents/{manager_id}/prompt
{"message": "Check the status of worker-alpha. Then stop it. Then check status again."}
```

**Expected:**
- Status check: IDLE
- Stop on IDLE agent: should be a no-op or succeed gracefully
- Status after stop: still IDLE (stop only affects RUNNING agents)
- Worker-alpha remains reusable

### Step 13: Full lifecycle — IDLE → RUNNING → IDLE → COMPLETED

Demonstrate the complete lifecycle on worker-alpha:

```
POST /agents/{manager_id}/prompt
{"message": "Send worker-alpha one final task: 'Say goodbye.' Then wait for it to finish and dismiss it."}
```

**Expected:**
- TASK: IDLE → RUNNING (auto-wake)
- Completion: RUNNING → IDLE
- Dismiss: IDLE → COMPLETED
- `GET /agents/{manager_id}/children` shows all children as COMPLETED

### Step 14: Message API — external message injection

Send a message directly via the REST API (simulating an external system):

```
POST /agents/{worker_alpha_id}/messages
{"content": "External system notification: build 42 passed.", "message_type": "status_update"}
```

**Expected:**
- Message created with `from_agent_id` defaulting to parent or "human"
- `MESSAGE_RECEIVED` event emitted
- Since worker-alpha is COMPLETED, this should fail with appropriate error

### Step 15: Collect observability data

```
GET /agents/{manager_id}/events
GET /agents/{worker_alpha_id}/events
GET /agents/{writer_id}/events
GET /agents/{manager_id}/children
GET /agents/{manager_id}/cost
```

## Success criteria

1. TASK messages trigger auto-wake on IDLE agents
2. QUESTION messages trigger auto-wake on IDLE agents
3. STATUS_UPDATE messages do NOT trigger auto-wake (message queued in inbox)
4. Queued messages are consumed when agent next wakes
5. Message direction filtering works (inbox/sent/all)
6. Guidance injection reaches a running agent's next LLM iteration
7. Stop transitions RUNNING → IDLE (agent remains reusable)
8. Dismiss transitions agent to COMPLETED (permanent, no more messages)
9. Sending to a COMPLETED agent fails with appropriate error
10. Stopped agents can be reused with new tasks (conversation preserved)
11. Full lifecycle: IDLE → RUNNING → IDLE → COMPLETED verified
12. Message events emitted: MESSAGE_SENT on sender, MESSAGE_RECEIVED on receiver
13. Messages consumed (deleted) after auto-wake delivery
14. External message injection via REST API works (or correctly rejects based on agent status)

## What to report

- Per agent: status transitions observed, event count by type
- Messages: count by type (task/result/question/answer/guidance/status_update)
- Auto-wake triggers: which message types triggered, which didn't
- Guidance injection: whether output reflected the guidance content
- Stop vs dismiss: status after each, reusability verified
- Error cases: error messages for rejected sends (to completed/failed agents)
- Message filtering: correct results for inbox/sent/all queries
- Event timeline showing MESSAGE_SENT/RECEIVED pairs
- Cost breakdown by model and by agent
- Any unexpected behavior: missed auto-wakes, unconsumed messages, wrong status transitions
