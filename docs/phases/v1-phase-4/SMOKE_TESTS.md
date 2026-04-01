# V1 Phase 4 — Smoke Tests

## Test Environment
- Prerequisites: V1 Phase 0–3 complete, `uv` installed
- Platform: must pass on both Linux (bash) and Windows (PowerShell)
- All LLM and embedding API calls are mocked
- Run: `cd backend && uv run pytest tests/smoke/ -k "v1_phase_4" -v --tb=short`

## ST-4.1: MemoryEntry model and MemoryType
- **Validates:** Memory data model
- **Method:** Import and instantiate models
- **Checks:**
  - `MemoryType` has EPISODIC, PREFERENCE, DECISION, OUTCOME, FACT, PROCEDURE
  - `MemoryEntry` can be created with content, agent_id, memory_type
  - Auto-generates id, timestamps, default importance and decay_score

## ST-4.2: Memory store CRUD and search
- **Validates:** SQLite memory store with cosine similarity search
- **Method:** Create temp DB, store entries with embeddings, search
- **Checks:**
  - Create memory entries with embeddings
  - Get by ID, list by agent_id
  - Delete by ID
  - Semantic search returns entries ranked by cosine similarity
  - Search filters by memory_type

## ST-4.3: Fake embedding provider
- **Validates:** Deterministic embedding provider for testing
- **Method:** Embed same text twice, different text once
- **Checks:**
  - Same text produces same embedding
  - Different texts produce different embeddings
  - `embed` and `embed_query` both work
  - Returned vectors have consistent dimensionality

## ST-4.4: Time decay strategy
- **Validates:** Memory decay scoring
- **Method:** Create entries with varying ages and access patterns
- **Checks:**
  - Recent memories get higher decay scores than old ones
  - Frequently accessed memories decay slower
  - High-importance memories decay slower
  - Decay score is between 0.0 and 1.0

## ST-4.5: Memory tools (remember, recall, forget)
- **Validates:** MemoryToolProvider implements ToolProvider
- **Method:** Create provider with mock embeddings, call tools
- **Checks:**
  - `list_tools()` returns 3 tools: remember, recall, forget
  - Calling `remember` stores a memory entry
  - Calling `recall` retrieves relevant memories by semantic search
  - Calling `forget` deletes a memory by ID
  - Events emitted for each operation

## ST-4.6: Context manager injects memories
- **Validates:** Context assembly with memory injection
- **Method:** Store memories, then assemble context for a query
- **Checks:**
  - Relevant memories are retrieved and injected as a system message
  - The injected message appears before the conversation history
  - When no relevant memories exist, no injection happens

## ST-4.7: Runtime integrates memory
- **Validates:** Agent runtime uses memory in its loop
- **Method:** Create agent, store memories, run with mock LLM
- **Checks:**
  - Memory tools are available in the tool list
  - Memories are injected into context before LLM call
  - MEMORY_READ events emitted during retrieval
