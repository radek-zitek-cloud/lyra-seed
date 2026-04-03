# UC-001: Greeting and Memory Verification

## Purpose

Verify that a new agent can receive a greeting with personal information, respond appropriately, automatically extract facts to memory, and recall those facts when asked.

## Preconditions

- Backend running at `http://localhost:8000`
- No specific DB state required (works with clean or existing DB)

## Steps

### Step 1: Create agent

```
POST /agents
{"name": "assistant"}
```

Record the agent ID. Verify config has:
- `model`: the platform's default model
- `auto_extract`: true
- `allowed_mcp_servers`: null (all)

### Step 2: Send greeting with personal information

```
POST /agents/{id}/prompt
{"message": "Hello! My name is Radek Zitek, I am the creator of this platform. I live in Prague, Czech Republic and I work as a cloud architect. Nice to meet you!"}
```

Wait for response. Then wait 5 seconds for async fact extraction to complete.

### Step 3: Verify auto-extraction

```
GET /memories
```

**Expected:** At least 3-4 new memories extracted:
- User's name (fact, importance >= 0.9)
- User's location (fact, importance >= 0.7)
- User's profession (fact, importance >= 0.8)
- User's role as platform creator (fact, importance >= 0.9)

All should be `public` visibility (fact type defaults to public).

### Step 4: Test memory recall

```
POST /agents/{id}/prompt
{"message": "What do you know about me? Can you recall anything from our conversation?"}
```

**Expected:**
- Agent should call the `recall` tool autonomously (not just rely on conversation history)
- Response should list all personal facts from Step 2
- If shared memories exist from other agents, those may also appear (expected behavior)

### Step 5: Collect observability data

```
GET /agents/{id}/events
GET /agents/{id}/conversations
GET /agents/{id}/cost
GET /memories
```

## Success criteria

1. Agent responds naturally to the greeting
2. Fact extraction produces 3+ memories with appropriate types and importance scores
3. Agent autonomously uses `recall` tool when asked about memories
4. All extracted facts are retrievable via the `recall` tool
5. Memory injection works — relevant memories appear in the conversation context on Turn 2
6. Cost is reasonable (< $0.10 for 2 turns)

## What to report

- Agent response text for each turn
- Event timeline with models and durations
- All extracted memories with types, importance, and visibility
- Whether `recall` was called autonomously
- Whether memory injection occurred (check for system message with "Relevant memories")
- Whether cross-agent memory sharing is observed (memories from other agents)
- Cost breakdown by model
- Any unexpected behavior
