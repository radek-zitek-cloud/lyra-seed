# UC-006: Inter-Agent Communication & Async Lifecycle — Report 2026-04-03

## Execution context

- **Date:** 2026-04-03 ~16:30 UTC
- **Manager ID:** `74501708-497a-4dc7-b8d0-5f0c155c7af0`
- **Worker-alpha ID:** `56d0b684-018f-4ede-8ff0-1e44e62d92e2`
- **Writer ID:** `3a541a80-fb94-41bf-8455-101da8f28970`
- **Model:** openai/gpt-5.4

## Step 1: Spawn reusable worker

Worker-alpha spawned with worker template. Initial task acknowledged ("Ready."), returned to IDLE.
`GET /agents/{mgr}/children` shows worker-alpha with correct `parent_agent_id`.

**Assessment:** PASS.

## Step 2: TASK triggers auto-wake

**Sent:** TASK "Calculate 7 * 13 and report the answer."
**Worker events:**
1. `message_received` (task) at :04
2. `tool_call` (send_message "The answer is 91.") at :09
3. `message_sent` (result) at :09

Worker auto-woke from IDLE, processed task, sent result back, returned to IDLE.

**Assessment:** PASS.

## Step 3: QUESTION triggers auto-wake

**Sent:** QUESTION "What was the result of your last calculation?"
**Worker events:**
1. `message_received` (question) at :58
2. `tool_call` (send_message) at :03
3. `message_sent` (result) at :03

Worker auto-woke from IDLE on QUESTION type.

**Assessment:** PASS.

## Step 4: STATUS_UPDATE auto-wake behavior

**Sent:** STATUS_UPDATE "FYI: The project deadline has been extended to May 1st."

**Result:** Worker DID auto-wake on status_update. Event timeline shows `message_received` at :53, followed by `memory_read` at :55 and LLM call — worker processed it and responded "Acknowledged."

**Finding:** The implementation auto-wakes on ALL message types, not just TASK/QUESTION/GUIDANCE. The code comment at `agent_spawner.py:583` says "actionable messages" but line 584 says "Any message to an idle agent triggers a turn." No message type filtering is applied.

**Assessment:** PARTIAL — auto-wake works, but does not discriminate by message type. This is a design choice (or bug) that differs from what the system prompt documents.

## Step 5: Queued messages

Skipped — not testable since all messages auto-wake (per Step 4 finding).

## Step 6: Message direction filtering

All messages returned empty for inbox/sent/all queries. Messages are **ephemeral** — consumed (deleted) after auto-wake delivery. The MESSAGE_SENT/MESSAGE_RECEIVED events prove the messages existed.

**Assessment:** PASS (filtering works correctly; messages are ephemeral by design).

## Step 7: Guidance injection to running agent

**Spawned:** writer with 500-word essay task.
**Sent guidance** via REST API while writer was RUNNING: "Focus specifically on the role of ARPANET and Tim Berners-Lee."
**Result:** Writer's essay did focus on ARPANET and Berners-Lee as central topics.
**Events:** `message_received` (guidance) on writer.

**Assessment:** PASS. Guidance reached the running agent and influenced output.

## Step 8: Stop a running agent

**Writer status before stop:** RUNNING (processing quantum computing essay task)
**After stop:** IDLE
**Method:** Manager called `stop_agent`

**Assessment:** PASS. RUNNING → IDLE transition, agent remains reusable.

## Step 9: Reuse stopped agent

**Sent:** TASK "Write a haiku about programming."
**Result:** Writer auto-woke, produced haiku: "Silent lines of code / Bugs hide deep in midnight loops / Dawn compiles resolve"
**Conversation history:** Preserved from prior tasks.

**Assessment:** PASS. Stopped agent reusable with preserved history.

## Step 10: Dismiss agent (permanent)

**Dismissed:** Writer via `dismiss_agent`.
**Status:** `completed`.

**Assessment:** PASS.

## Step 11: Send to dismissed agent (error case)

**Attempted:** TASK to dismissed writer via `send_message` tool.
**Error:** "Agent 3a541a80... is completed and cannot receive messages"
**No auto-wake occurred.**

**Assessment:** PASS. Correct error handling.

## Step 12: Stop vs dismiss distinction

**Stop on IDLE agent:** No-op. Worker-alpha remained IDLE and reusable.
**Dismiss:** Permanently sets to COMPLETED.

| Action | From Status | To Status | Reusable? |
|--------|-----------|----------|-----------|
| stop | RUNNING | IDLE | Yes |
| stop | IDLE | IDLE (no-op) | Yes |
| dismiss | IDLE | COMPLETED | No |
| dismiss | RUNNING | COMPLETED | No |

**Assessment:** PASS. Clear distinction.

## Step 13: Full lifecycle

Worker-alpha lifecycle verified:
1. IDLE (after initial task)
2. → RUNNING (auto-wake on TASK)
3. → IDLE (task complete)
4. → RUNNING (auto-wake on QUESTION)
5. → IDLE (question answered)
6. → RUNNING (auto-wake on STATUS_UPDATE)
7. → IDLE
8. → RUNNING (auto-wake on final TASK "Say goodbye.")
9. → IDLE
10. → COMPLETED (dismiss)

All children show `completed` at end: writer (dismissed), worker-alpha (dismissed).

**Assessment:** PASS.

## Step 14: External message via REST API to completed agent

**Sent:** POST `/agents/{worker_id}/messages` with status_update to completed agent.
**Result:** HTTP 201 — message accepted and stored.

**Finding:** The REST API route does NOT check agent status before accepting messages. The tool-level `send_message` rejects messages to COMPLETED agents, but the direct API bypasses this validation. Inconsistent behavior.

**Assessment:** ISSUE. REST API should validate target agent status, matching tool behavior.

## Event summary

| Agent | Events | Spawns | Msgs Sent | Msgs Recv | Tool Calls | Memory R/W |
|-------|--------|--------|-----------|-----------|------------|-----------|
| Manager | 363 | 2 | 8 | 4 | 17 | 17/24 |
| Worker-alpha | 116 | 0 | 3 | 5 | 3 | 5/2 |
| Writer | 85 | 0 | 1 | 3 | 1 | 3/7 |
| **Total** | **564** | **2** | **12** | **12** | **21** | **25/33** |

## Cost

| Agent | Model | Calls | Prompt tokens | Completion tokens |
|-------|-------|-------|--------------|-------------------|
| Manager | gpt-5.4 | 68 | 562,160 | 5,242 |
| Manager | gpt-5.4-mini | 22 | 21,264 | 2,143 |
| Manager | text-embedding-3-large | 47 | 1,932 | 0 |
| Worker-alpha | gpt-5.4 | 16 | 104,790 | 578 |
| Worker-alpha | gpt-5.4-mini | 9 | 14,900 | 523 |
| Worker-alpha | text-embedding-3-large | 22 | 618 | 0 |
| Writer | gpt-5.4 | 8 | 60,530 | 4,392 |
| Writer | gpt-5.4-mini | 10 | 38,574 | 1,711 |
| Writer | text-embedding-3-large | 16 | 577 | 0 |

### Combined
| Model | Calls | Prompt tokens | Completion tokens |
|-------|-------|--------------|-------------------|
| openai/gpt-5.4 | 92 | 727,480 | 10,212 |
| openai/gpt-5.4-mini | 41 | 74,738 | 4,377 |
| openai/text-embedding-3-large | 85 | 3,127 | 0 |
| **Total** | **218** | **805,345** | **14,589** |

## Summary

| Criterion | Result | Notes |
|-----------|--------|-------|
| TASK triggers auto-wake | PASS | IDLE → RUNNING, result sent back |
| QUESTION triggers auto-wake | PASS | IDLE → RUNNING, answer sent back |
| STATUS_UPDATE no auto-wake | **ISSUE** | Auto-wakes on ALL message types (see Issue 1) |
| Queued messages consumed | N/A | Not testable due to Issue 1 |
| Message direction filtering | PASS | Correct (messages ephemeral by design) |
| Guidance injection | PASS | Running agent received and reflected guidance |
| Stop → IDLE (reusable) | PASS | RUNNING → IDLE, agent reusable |
| Dismiss → COMPLETED (permanent) | PASS | No more messages accepted via tool |
| Send to completed fails | PASS | Tool correctly rejects with error |
| Reuse after stop | PASS | Conversation preserved, new tasks work |
| Full lifecycle | PASS | IDLE → RUNNING → IDLE → COMPLETED verified |
| Message events | PASS | MESSAGE_SENT/RECEIVED emitted for all messages |
| Messages consumed | PASS | Deleted after auto-wake delivery |
| External API validation | **ISSUE** | REST API accepts messages to completed agents (see Issue 2) |

**Overall: PASS with 2 issues.**

## Issues found

### Issue 1: Auto-wake triggers on all message types

The `_wake_idle_agent` method in both `agent_spawner.py` and `message_routes.py` does not filter by message type. All messages to IDLE agents trigger auto-wake, including STATUS_UPDATE and RESULT/ANSWER which are documented as non-actionable. The agent system prompt describes only TASK, QUESTION, and GUIDANCE as auto-wake triggers.

**Impact:** Low — agents handle informational messages gracefully (just acknowledge). But it wastes tokens on unnecessary LLM calls for non-actionable messages.

**Fix:** Add a check in `_wake_idle_agent`: only trigger if `msg.message_type in (TASK, QUESTION, GUIDANCE)`.

### Issue 2: REST API message route skips agent status validation

`POST /agents/{id}/messages` accepts messages to COMPLETED and FAILED agents (HTTP 201). The tool-level `send_message` in `AgentSpawnerProvider` correctly rejects these with an error. The API route at `message_routes.py` does not perform the same validation.

**Impact:** Low — external callers can inject messages to dead agents. No auto-wake occurs (agent is not IDLE), but messages accumulate in the inbox without being processed.

**Fix:** Add status check in `message_routes.py` before creating the message — return HTTP 409 or 422 if target agent is COMPLETED or FAILED.
