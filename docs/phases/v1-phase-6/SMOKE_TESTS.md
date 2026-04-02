# V1 Phase 6 — Smoke Tests

## Test Environment
- Prerequisites: phases 0–5 complete, backend dependencies installed
- Platform: must pass on both Linux (bash) and Windows (PowerShell)
- LLM calls: always mocked
- External APIs: never called

## Backend Smoke Tests

### ST-6.1: Retry on 429
- **Validates:** LLM provider retries on HTTP 429 (rate limit)
- **Method:** Mock httpx to return 429→429→200 sequence
- **Checks:**
  - Three HTTP calls made (2 retries + 1 success)
  - Final result is successful LLM response

### ST-6.2: No retry on 500
- **Validates:** LLM provider does NOT retry on HTTP 500 (server error)
- **Method:** Mock httpx to return 500
- **Checks:**
  - Only a single HTTP call made
  - Error raised to caller

### ST-6.3: Retry on timeout
- **Validates:** LLM provider retries on `httpx.TimeoutException`
- **Method:** Mock httpx to raise TimeoutException then return 200
- **Checks:**
  - Two calls made (1 retry + 1 success)
  - Final result is successful

### ST-6.4: HITL timeout
- **Validates:** HITL gate times out after configured duration
- **Method:** Set `hitl_timeout_seconds=0.1`, trigger HITL gate, don't respond
- **Checks:**
  - Gate unblocks after timeout
  - Agent status returns to IDLE (not FAILED)
  - HITL_RESPONSE event emitted with `timed_out: True`

### ST-6.5: Stuck agent cleanup
- **Validates:** Agents stuck in RUNNING/WAITING_HITL are cleaned up on startup
- **Method:** Create agents with status RUNNING and WAITING_HITL directly in DB, call `cleanup_stuck_agents()`
- **Checks:**
  - Stuck agents reset to IDLE status
  - Non-stuck agents (IDLE, COMPLETED) unchanged

### ST-6.6: Memory prune
- **Validates:** Old, low-importance memories are pruned
- **Method:** Create memories with old timestamps and low importance, call `prune()`
- **Checks:**
  - Memories below threshold are deleted
  - Prune returns count of deleted entries

### ST-6.7: High-importance survives prune
- **Validates:** Important memories survive despite age
- **Method:** Create old memory with high importance (1.0), call `prune()`
- **Checks:**
  - High-importance memory not deleted
  - Memory still retrievable after prune

### ST-6.8: Context truncation
- **Validates:** Long conversations are truncated to fit token budget
- **Method:** Create 200 long messages with a small token budget (200 tokens)
- **Checks:**
  - Output has fewer messages than input
  - System prompt is preserved (never truncated)
  - Truncation marker message present

### ST-6.9: Cost aggregation
- **Validates:** Cost is computed correctly from LLM_RESPONSE events
- **Method:** Emit mock LLM_RESPONSE events with known token counts and model names
- **Checks:**
  - Total prompt_tokens and completion_tokens aggregated correctly
  - Cost computed using model-specific pricing
  - by_model breakdown includes call counts

### ST-6.10: Cost API endpoint
- **Validates:** `GET /agents/{id}/cost` returns cost data
- **Method:** Create agent, emit LLM_RESPONSE events, call cost endpoint
- **Checks:**
  - Returns 200 with `total_cost_usd`, `total_prompt_tokens`, `total_completion_tokens`
  - `by_model` breakdown present
