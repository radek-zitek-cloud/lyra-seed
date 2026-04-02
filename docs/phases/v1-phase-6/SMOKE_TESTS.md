# V1 Phase 6 — Smoke Tests

## ST-6.1: Retry on 429
Mock 429→429→200, verify 3 calls, success returned.

## ST-6.2: No retry on 500
Mock 500, verify single call, error raised.

## ST-6.3: Retry on timeout
Mock TimeoutException→success, verify retry.

## ST-6.4: HITL timeout
Set 0.1s timeout, verify gate times out, status IDLE.

## ST-6.5: Stuck agent cleanup
Create stuck agents in DB, verify cleanup resets to IDLE.

## ST-6.6: Memory prune
Create old low-importance memories, verify prune deletes them.

## ST-6.7: High-importance survives prune
Important memories survive despite age.

## ST-6.8: Context truncation
200 long messages with small budget, verify truncation + system prompt preserved.

## ST-6.9: Cost aggregation
Emit mock LLM events, verify cost computation.

## ST-6.10: Cost API endpoint
GET /agents/{id}/cost returns correct data.
