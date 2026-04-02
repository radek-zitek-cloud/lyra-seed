# V1 Phase 6 — Plan

## Phase Reference
- **Version:** V1
- **Phase:** 6
- **Title:** Pre-V2 Hardening
- **Scope:** LLM retry, HITL timeout, memory GC, context compression, cost tracking

## Prerequisites
- V1 Phase 0–5 — COMPLETE

## Deliverables
- [ ] LLM retry with exponential backoff (429/5xx/timeout)
- [ ] HITL timeout + stuck agent cleanup on startup
- [ ] Memory GC: wire decay strategy, prune after each run
- [ ] Context compression: token estimation + sliding window truncation
- [ ] Cost tracking: aggregate from events, expose via API
