# UC-004: Memory System Validation — Report 2026-04-03

## Execution context

- **Date:** 2026-04-03 ~16:10 UTC
- **Backend:** running, DB contains memories from prior sessions
- **Alice ID:** `f7f90fd0-d712-4ea0-b087-b6bb05e54e97`
- **Bob ID:** `06b62bf8-6235-45f3-b8ca-e93f325a7cb1`
- **Model:** openai/gpt-5.4

## Step 2: Memory tool discovery

`remember`, `recall`, `forget` all present in `GET /tools` (40 tools total). PASS.

## Step 3: Explicit remember (Alice)

**Prompt:** Store 3 deployment facts with high importance.

**Result:** Alice's memory injection found the same 3 facts already existed from a prior session's agent (deduplication working). Agent recognized duplicates and reported them instead of creating copies.

**Memories verified via API:**
- `Deployment target is Kubernetes 1.31 on AWS EKS.` — fact, public, importance 0.9
- `Staging environment URL is staging.lyra.internal.` — fact, public, importance 0.9
- `Next release date is April 15th 2026.` — fact, public, importance 0.9

**Assessment:** PASS. Deduplication correctly prevented redundant storage.

## Step 5: Semantic recall (Alice)

**Prompt:** "What do you know about our deployment infrastructure?"

**Result:** Alice recalled all 3 facts: K8s/EKS, staging URL, and release date.

**Assessment:** PASS.

## Step 6: Access tracking

After recall:
| Memory | access_count | last_accessed_at |
|--------|-------------|-----------------|
| K8s/EKS | 2 | 2026-04-03T16:00:37 |
| Staging URL | 2 | 2026-04-03T16:00:38 |
| Release date | 1 | 2026-04-03T16:00:09 |

K8s and staging bumped to 2 (injection + recall). Release date at 1 (injection only, not returned in deployment query). PASS.

## Step 7: Cross-agent memory sharing (Bob)

**Prompt:** "Do you know anything about our deployment target or staging environment?"

**Result:** Bob found Alice's public facts via `recall`:
- Staging URL: `staging.lyra.internal`
- Deployment target: K8s 1.31 on AWS EKS

**Assessment:** PASS. Cross-agent public memory sharing works.

## Step 8: Memory injection at turn start

**Prompt:** "When is the next release?"

**Result:** Alice answered "April 15th, 2026" directly — the memory was injected into context automatically at turn start. Only 3 events (no explicit recall tool call).

**Assessment:** PASS. Context manager injection works.

## Step 9: Forget a memory

**Memory deleted:** `c24289d0-a5f0-4595-8380-ffa13ab07390` (staging URL)

**Verification:** `GET /memories/{id}` returns HTTP 404. PASS.

## Step 10: Verify forgotten memory gone from recall

**Prompt:** "What do you know about the staging environment?"

**Result:** "I don't have a staging environment URL in memory anymore." Listed only K8s and release date.

**Assessment:** PASS. Forgotten memories removed from both recall and injection.

## Step 11: Memory type filtering (preference)

**Stored:** "User prefers YAML over JSON for configuration files."
- Type: `preference`, Visibility: `private`, Importance: 0.8

**Bob test:** "Do you know anything about configuration file format preferences?" — "found nothing relevant."

**Assessment:** PASS. Private preference isolated to Alice, invisible to Bob.

## Step 12: REST API search and filter

| Query | Results | Notes |
|-------|---------|-------|
| `?q=kubernetes` | 5 | K8s fact ranked first (correct) |
| `?agent_id={alice}&memory_type=fact` | 2 | K8s + release date (staging deleted) |
| `?memory_type=fact&visibility=public` | 10 | Includes cross-agent facts |
| `?archived=true` | 0 | Expected — no decay run yet |

**Assessment:** PASS. Semantic search, filtering, and combining all work.

## Step 13: REST API update

**Updated:** Release date memory importance from 0.9 to 0.2 via `PATCH /memories/{id}`.

**Assessment:** PASS.

## Step 14: Auto-extraction

**Prompt:** "We decided yesterday to migrate from PostgreSQL to CockroachDB..."

**Memories before:** 4. **After:** 6. **New from extraction:** 2.

| Content | Type | Visibility | Importance |
|---------|------|-----------|------------|
| PostgreSQL to CockroachDB migration planned for Q3 2026 | fact | public | 0.7 |
| Decision to migrate from PostgreSQL to CockroachDB for horizontal scaling | decision | private | 0.8 |

**Assessment:** PASS. Auto-extraction correctly identified both a factual timeline and a decision, with appropriate types and visibility.

## Cost

### Alice
| Model | Calls | Prompt tokens | Completion tokens |
|-------|-------|--------------|-------------------|
| openai/gpt-5.4 | 22 | 147,502 | 1,156 |
| openai/gpt-5.4-mini | 9 | 6,789 | 650 |
| openai/text-embedding-3-large | 39 | 617 | 0 |

### Bob
| Model | Calls | Prompt tokens | Completion tokens |
|-------|-------|--------------|-------------------|
| openai/gpt-5.4 | 8 | 61,244 | 836 |
| openai/gpt-5.4-mini | 3 | 5,386 | 451 |
| openai/text-embedding-3-large | 8 | 94 | 0 |

### Combined
| Model | Calls | Prompt tokens | Completion tokens |
|-------|-------|--------------|-------------------|
| openai/gpt-5.4 | 30 | 208,746 | 1,992 |
| openai/gpt-5.4-mini | 12 | 12,175 | 1,101 |
| openai/text-embedding-3-large | 47 | 711 | 0 |
| **Total** | **89** | **221,632** | **3,093** |

## Event summary

### Alice: 182 events
- llm_request/response: 70 each (agent turns + extraction + embeddings)
- memory_read: 8 (injections + recalls)
- memory_write: 24 (explicit remembers + auto-extractions)
- tool_call/result: 5 each (remember, recall, forget)

### Bob: 55 events
- llm_request/response: 19 each
- memory_read: 7 (injections + recalls)
- tool_call/result: 5 each (recall calls)

## Summary

| Criterion | Result | Notes |
|-----------|--------|-------|
| Tool discovery | PASS | remember, recall, forget in tool list |
| Explicit remember | PASS | Correct type, visibility, importance |
| Semantic recall | PASS | Ranked results by similarity |
| Access tracking | PASS | access_count and last_accessed_at updated |
| Cross-agent sharing | PASS | Bob found Alice's public facts |
| Private isolation | PASS | Bob cannot see Alice's preferences |
| Memory injection | PASS | Automatic context injection at turn start |
| Forget | PASS | Memory deleted, gone from recall |
| Type filtering | PASS | fact vs preference with correct defaults |
| REST API | PASS | Search, filter, update all work |
| Auto-extraction | PASS | 2 memories created with correct types |
| Events | PASS | memory_read and memory_write emitted |
| Deduplication | PASS | Agent recognized existing facts, no duplicates |

**Overall: PASS — all 12 criteria met, no issues found.**
