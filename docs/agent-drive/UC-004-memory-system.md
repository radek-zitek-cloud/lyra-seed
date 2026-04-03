# UC-004: Memory System Validation

## Purpose

Verify the full memory system end-to-end: explicit remember/recall/forget tools, semantic search, cross-agent memory sharing via visibility, automatic memory injection at turn start, memory decay and archival, access tracking, and the REST API for memory management. Validates V1 Phase 4 deliverables.

## Preconditions

- Backend running at `http://localhost:8000`
- Ideally a clean DB (or acceptance that prior memories may appear in searches)
- `auto_extract: true` in agent config (default)

## Steps

### Step 1: Create two agents

```
POST /agents
{"name": "alice"}

POST /agents
{"name": "bob"}
```

Record both agent IDs. Two agents are needed to test cross-agent memory sharing.

### Step 2: Verify memory tools in tool list

```
GET /tools
```

**Expected:** `remember`, `recall`, and `forget` appear as `prompt_macro` type tools from `memory` source.

### Step 3: Explicit remember (agent Alice)

```
POST /agents/{alice_id}/prompt
{"message": "Please remember the following facts: 1) Our deployment target is Kubernetes 1.31 on AWS EKS. 2) The staging environment URL is staging.lyra.internal. 3) Our next release date is April 15th 2026. Store each as a separate fact with high importance."}
```

**Expected:**
- Agent calls `remember` tool 3 times (once per fact)
- Each call stores a `fact` type memory with `public` visibility
- Response confirms all three facts were stored
- Events panel shows 3 `memory_write` events with `source: "remember"`

### Step 4: Verify memories via REST API

```
GET /memories?agent_id={alice_id}&memory_type=fact
```

**Expected:**
- At least 3 memories with the stored content
- Each has: `memory_type: "fact"`, `visibility: "public"`, `importance >= 0.7`
- Each has `access_count: 0`, `archived: false`
- `decay_score` close to 1.0 (freshly created)

### Step 5: Semantic recall (agent Alice)

```
POST /agents/{alice_id}/prompt
{"message": "What do you know about our deployment infrastructure?"}
```

**Expected:**
- Agent calls `recall` tool with a query about deployment/infrastructure
- Response includes the Kubernetes/EKS fact and possibly the staging URL
- Events show `memory_read` event with `results_count >= 1`

### Step 6: Verify access tracking

```
GET /memories?agent_id={alice_id}&memory_type=fact
```

**Expected:** The recalled memories now have `access_count >= 1` and `last_accessed_at` updated to a recent timestamp.

### Step 7: Cross-agent memory sharing (agent Bob)

```
POST /agents/{bob_id}/prompt
{"message": "Do you know anything about our deployment target or staging environment? Search your memories."}
```

**Expected:**
- Bob calls `recall` and finds Alice's public facts (Kubernetes, staging URL)
- Response references the facts originally stored by Alice
- Bob does not see any of Alice's private memories (if any exist)
- Events show `memory_read` with results from cross-agent search

### Step 8: Memory injection at turn start

```
POST /agents/{alice_id}/prompt
{"message": "When is the next release?"}
```

**Expected:**
- Before the LLM call, the context manager injects relevant memories as a system message
- The agent answers with the April 15th date
- This may come from memory injection (automatic) or recall tool (explicit) — either is acceptable
- Check events for `memory_read` at the start of the turn (injection) vs. `tool_call` for recall

### Step 9: Forget a memory

First, get the memory ID for the staging URL fact:
```
GET /memories?agent_id={alice_id}&q=staging
```

Then ask Alice to forget it:
```
POST /agents/{alice_id}/prompt
{"message": "Please forget the memory about the staging environment URL. The memory ID is {memory_id}."}
```

**Expected:**
- Agent calls `forget` tool with the memory ID
- Response confirms the memory was deleted
- `GET /memories/{memory_id}` returns 404

### Step 10: Verify forgotten memory is gone from recall

```
POST /agents/{alice_id}/prompt
{"message": "What do you know about the staging environment?"}
```

**Expected:**
- Agent calls `recall` but does not find the deleted staging URL memory
- Response indicates no information about staging (or only from conversation history, not memory)

### Step 11: Test memory type filtering

```
POST /agents/{alice_id}/prompt
{"message": "Remember that I prefer YAML over JSON for configuration files. Store this as a preference."}
```

Then verify:
```
GET /memories?agent_id={alice_id}&memory_type=preference
```

**Expected:**
- Memory stored with `memory_type: "preference"`, `visibility: "private"` (preference defaults to private)
- Does not appear when Bob searches (private to Alice)

### Step 12: REST API — search and filter

```
GET /memories?q=kubernetes
GET /memories?agent_id={alice_id}
GET /memories?memory_type=fact&visibility=public
GET /memories?archived=true
```

**Expected:**
- Semantic search returns ranked results by relevance
- Agent filter returns only that agent's memories
- Type + visibility filters combine correctly
- Archived filter returns only archived memories (may be empty if no decay has run)

### Step 13: REST API — update memory

Pick a memory and update its importance:
```
PATCH /memories/{memory_id}
{"importance": 0.2}
```

**Expected:** Memory importance updated. Lower importance will cause faster decay.

### Step 14: Auto-extraction verification

```
POST /agents/{alice_id}/prompt
{"message": "We decided yesterday to migrate from PostgreSQL to CockroachDB for better horizontal scaling. The migration is planned for Q3 2026."}
```

Wait 5 seconds for async extraction, then:
```
GET /memories?agent_id={alice_id}
```

**Expected:**
- Auto-extraction creates 1-2 new memories (decision about DB migration, timeline)
- Memories have `source: "auto_extract"` in their creation event
- Events show `memory_write` with `source: "auto_extract"`

### Step 15: Collect observability data

```
GET /agents/{alice_id}/events
GET /agents/{bob_id}/events
GET /memories
GET /agents/{alice_id}/cost
GET /agents/{bob_id}/cost
```

## Success criteria

1. Memory tools (`remember`, `recall`, `forget`) appear in the tool list
2. Explicit `remember` stores memories with correct type, visibility, and importance
3. Semantic `recall` returns relevant memories ranked by similarity
4. Access tracking updates `access_count` and `last_accessed_at` on recall
5. Cross-agent sharing works — public memories are visible to other agents
6. Private memories are isolated to the owning agent
7. Memory injection works — relevant memories are provided at turn start
8. `forget` deletes memories and they no longer appear in recall
9. Memory type filtering works (fact vs preference vs decision)
10. REST API supports semantic search, filtering, and updates
11. Auto-extraction creates memories from conversation content
12. All memory operations emit appropriate events (`memory_read`, `memory_write`)

## What to report

- Memory count by type and visibility after all steps
- Each `remember` call: content stored, type, importance, visibility, memory ID
- Each `recall` call: query, result count, whether cross-agent results appeared
- Whether memory injection occurred (check for system message in conversation)
- Access count changes after recall
- Auto-extraction: count of memories created, types, importance scores
- Forget verification: memory removed from search results
- Event timeline for each agent (memory_read, memory_write events)
- Cost breakdown by model
- Any unexpected behavior (wrong visibility, missing memories, stale results)
