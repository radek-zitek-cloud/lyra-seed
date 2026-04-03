# UC-005: Multi-Agent Orchestration

## Purpose

Verify V2 multi-agent capabilities end-to-end: sub-agent spawning and lifecycle, inter-agent messaging with auto-wake, reusable workers, and orchestration patterns (sequential, parallel, pipeline) with result synthesis. Validates V2 Phases 1–3.

## Preconditions

- Backend running at `http://localhost:8000`
- MCP servers configured (filesystem + shell) for tool-using sub-agents
- Agent templates `worker` and `coder` exist in `prompts/`
- No specific DB state required

## Steps

### Step 1: Create parent agent and spawn a child

```
POST /agents
{"name": "coordinator"}

POST /agents/{coordinator_id}/prompt
{"message": "Spawn a sub-agent named 'researcher' using the worker template. Give it this task: 'List three advantages of event-driven architecture and return the result.'"}
```

**Expected:**
- Agent calls `spawn_agent` with name "researcher" and template "worker"
- Returns immediately with `child_agent_id` (async spawn)
- `AGENT_SPAWN` event emitted on the parent with child ID and task preview
- Child starts running in the background
- `GET /agents/{coordinator_id}/children` shows the child with its status

### Step 2: Wait for child result

```
POST /agents/{coordinator_id}/prompt
{"message": "Wait for the researcher to finish and tell me what it found."}
```

**Expected:**
- Agent calls `wait_for_agent` with the child's ID
- Blocks until child completes (or timeout)
- Returns the child's response content
- `AGENT_COMPLETE` event emitted on the child
- Child status transitions: RUNNING → IDLE

### Step 3: Reuse the worker with a new task via messaging

```
POST /agents/{coordinator_id}/prompt
{"message": "Send the researcher a new task: 'Now list three disadvantages of event-driven architecture.'"}
```

**Expected:**
- Agent calls `send_message` with `message_type: "task"`
- `MESSAGE_SENT` event on parent, `MESSAGE_RECEIVED` event on child
- Auto-wake triggers: child wakes from IDLE and processes the new task
- Child sends result back via `send_message` with `message_type: "result"`
- Parent auto-wakes and reports the result
- `GET /agents/{coordinator_id}/messages` shows the exchange
- `GET /agents/{researcher_id}/messages` shows the exchange from the child's perspective

### Step 4: Check agent status (non-blocking)

```
POST /agents/{coordinator_id}/prompt
{"message": "Check the status of the researcher agent."}
```

**Expected:**
- Agent calls `check_agent_status` (non-blocking)
- Returns child's current status (IDLE) and a preview of its last message

### Step 5: List all children

```
POST /agents/{coordinator_id}/prompt
{"message": "List all your sub-agents."}
```

**Expected:**
- Agent calls `list_child_agents`
- Returns at least the researcher with name, ID, and status
- Matches `GET /agents/{coordinator_id}/children`

### Step 6: Dismiss the worker

```
POST /agents/{coordinator_id}/prompt
{"message": "Dismiss the researcher agent — we're done with it."}
```

**Expected:**
- Agent calls `dismiss_agent`
- Child status changes to COMPLETED (no longer reusable)
- Subsequent task messages to this child should not auto-wake it

### Step 7: Orchestration — parallel strategy

```
POST /agents/{coordinator_id}/prompt
{"message": "Orchestrate this task with parallel strategy: Compare Python, Rust, and Go for building CLI tools. Research each language independently, covering performance, ecosystem, developer experience, and binary distribution. Then synthesize a recommendation."}
```

**Expected:**
- Agent calls `orchestrate` with `strategy: "parallel"`
- Decomposer creates 3+ subtasks (one per language) plus a synthesis step
- Independent subtasks run concurrently (check event timestamps for overlap)
- Each subtask produces a result
- Auto-synthesis combines all results into a unified recommendation
- Events: `orchestration.plan_created`, per-subtask `orchestration.subtask_started`/`completed`, `orchestration.synthesis_completed`
- Final response is a coherent comparison, not just concatenated results

### Step 8: Orchestration — sequential strategy

```
POST /agents/{coordinator_id}/prompt
{"message": "Orchestrate this task sequentially: First, define what 'observability' means in the context of distributed systems. Then, list the three pillars of observability. Finally, explain how each pillar applies to a microservices architecture."}
```

**Expected:**
- Agent calls `orchestrate` with `strategy: "sequential"`
- Subtasks execute in order (each starts after previous completes)
- Each subtask builds on context from the conversation
- Synthesis produces a structured, coherent explanation
- Event timeline shows non-overlapping subtask execution

### Step 9: Orchestration — pipeline strategy

```
POST /agents/{coordinator_id}/prompt
{"message": "Orchestrate this as a pipeline: Start with a raw idea — 'a tool that helps developers write better commit messages.' Then refine it into a product spec. Then identify the top 3 technical risks. Then propose mitigations for each risk."}
```

**Expected:**
- Agent calls `orchestrate` with `strategy: "pipeline"`
- Subtask 1 output feeds as context into subtask 2
- Subtask 2 output feeds into subtask 3, and so on
- Each stage visibly builds on the previous stage's output
- Final synthesis captures the full pipeline progression

### Step 10: Orchestration — decompose only (no execution)

```
POST /agents/{coordinator_id}/prompt
{"message": "Decompose this task into subtasks but don't execute it: Build a comprehensive test suite for a REST API that handles user authentication, including unit tests, integration tests, and load tests."}
```

**Expected:**
- Agent calls `decompose_task` (not `orchestrate`)
- Returns a plan with subtasks, dependencies, assigned_to, failure policies
- No subtask execution occurs
- Plan shows a logical decomposition with dependency chains

### Step 11: Inter-agent question/answer flow

Spawn a new specialist and test Q&A messaging:

```
POST /agents/{coordinator_id}/prompt
{"message": "Spawn a sub-agent named 'advisor' with the worker template and task 'You are a security advisor. Wait for questions and answer them.' Then send it a question: 'What are the OWASP top 3 web vulnerabilities?'"}
```

**Expected:**
- Parent spawns advisor, then sends a `question` type message
- Advisor auto-wakes, processes the question
- Advisor sends back an `answer` type message
- Parent auto-wakes and relays the answer
- Message types are correct in `GET /agents/{id}/messages`

### Step 12: Cross-agent memory via sub-agents

```
POST /agents/{coordinator_id}/prompt
{"message": "Remember that our API rate limit is 1000 requests per minute. Store this as a fact with high importance."}
```

Then ask the advisor (child):

```
POST /agents/{advisor_id}/prompt
{"message": "What do you know about our API rate limits? Search your memories."}
```

**Expected:**
- Parent stores the fact as public memory
- Child can recall it via cross-agent memory sharing
- Child's response references the 1000 req/min limit

### Step 13: Collect observability data

```
GET /agents/{coordinator_id}/events
GET /agents/{coordinator_id}/children
GET /agents/{coordinator_id}/messages
GET /agents/{researcher_id}/events
GET /agents/{advisor_id}/events
GET /agents/{coordinator_id}/cost
```

## Success criteria

1. Sub-agent spawning works — child created with correct parent linkage and template config
2. Async spawn — parent returns immediately, child runs in background
3. Wait for agent — parent blocks until child finishes, receives result
4. Reusable workers — idle child accepts new tasks via messaging without re-spawn
5. Auto-wake — sending a TASK/QUESTION to an IDLE child triggers execution
6. Message passing — TASK, RESULT, QUESTION, ANSWER types flow correctly between agents
7. Dismiss — child transitions to COMPLETED and is no longer reusable
8. Parallel orchestration — independent subtasks run concurrently with overlapping timestamps
9. Sequential orchestration — subtasks execute one at a time in order
10. Pipeline orchestration — each subtask's output feeds into the next as context
11. Decompose without execute — returns a plan with subtasks and dependencies, no execution
12. Result synthesis — orchestrated results are combined into a coherent unified response
13. Cross-agent memory — child can recall parent's public memories
14. Event observability — AGENT_SPAWN, AGENT_COMPLETE, MESSAGE_SENT, MESSAGE_RECEIVED, orchestration events all emitted
15. Agent hierarchy visible via API — `/children` and `/messages` endpoints return correct data

## What to report

- Per agent: event count by type, conversation turn count
- Spawn: child agent IDs, templates used, parent linkage verified
- Messages: count by type (task/result/question/answer), auto-wake triggers observed
- Orchestration: strategy used, subtask count, execution time per subtask, parallelism evidence (timestamp overlap)
- Synthesis quality: whether the combined result is coherent vs. just concatenated
- Decompose plan: subtask descriptions, dependencies, failure policies
- Reuse: number of tasks sent to the same worker without re-spawn
- Cross-agent memory: whether child found parent's facts
- Cost breakdown by model and by agent
- Event timeline for the coordinator (parent) showing the full multi-agent flow
- Any unexpected behavior: failed spawns, missed auto-wakes, stale messages, wrong status transitions
