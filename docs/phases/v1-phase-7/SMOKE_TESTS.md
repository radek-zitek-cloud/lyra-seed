# V1 Phase 7 — Smoke Tests

## Test Environment
- Prerequisites: phases 0–6 complete, backend dependencies installed
- Platform: must pass on both Linux (bash) and Windows (PowerShell)
- LLM calls: always mocked
- External APIs: never called

## Backend Smoke Tests

### ST-7.1: Visibility enum
- **Validates:** `MemoryVisibility` enum exists with PRIVATE, TEAM, PUBLIC, INHERIT values
- **Method:** Import enum, create MemoryEntry with visibility field
- **Checks:**
  - All four enum values importable
  - MemoryEntry accepts visibility parameter
  - Default visibility is PRIVATE

### ST-7.2: Visibility roundtrip
- **Validates:** Visibility persists through ChromaDB storage and retrieval
- **Method:** Store a PUBLIC MemoryEntry, retrieve by ID
- **Checks:**
  - Stored entry has PUBLIC visibility
  - Retrieved entry has PUBLIC visibility (not lost in serialization)

### ST-7.3: Cross-agent public search
- **Validates:** PUBLIC memories are visible to other agents
- **Method:** Agent A stores a PUBLIC DOMAIN_KNOWLEDGE memory, Agent B searches with `include_public=True`
- **Checks:**
  - Agent B's search returns Agent A's public memory
  - Content matches the stored memory

### ST-7.4: Private stays private
- **Validates:** PRIVATE memories are NOT visible to other agents
- **Method:** Agent A stores a PRIVATE PREFERENCE memory, Agent B searches with `include_public=True`
- **Checks:**
  - Agent B's search does NOT return Agent A's private memory

### ST-7.5: Summarization replaces truncation
- **Validates:** Context compression uses LLM summarization instead of simple truncation
- **Method:** Create 50 long messages exceeding a small token budget (200 tokens), with mock LLM returning a summary
- **Checks:**
  - Result contains "Summary" (from mock LLM output), not the truncation marker
  - Output has fewer messages than input

### ST-7.6: Summary saved as episodic
- **Validates:** Context summary is saved as an EPISODIC memory in ChromaDB
- **Method:** Trigger summarization via ContextManager.assemble() with messages over token budget
- **Checks:**
  - At least one EPISODIC memory entry exists for the agent
  - Entry content contains the summary text

### ST-7.7: Fallback truncation
- **Validates:** Falls back to truncation when no LLM provider is configured
- **Method:** Create ContextManager without llm_provider
- **Checks:**
  - ContextManager can be created without LLM
  - `_llm` is None (will use truncation path)

### ST-7.8: Extraction produces entries
- **Validates:** FactExtractor creates memory entries from conversation
- **Method:** Mock LLM returns JSON with one preference extraction, call `extractor.extract()`
- **Checks:**
  - One memory entry returned
  - Content matches extracted text ("User prefers dark mode")
  - memory_type is "preference"
  - importance is 0.8

### ST-7.9: Domain knowledge defaults public
- **Validates:** Extracted DOMAIN_KNOWLEDGE entries default to PUBLIC visibility
- **Method:** Mock LLM returns domain_knowledge extraction, call `extractor.extract()`
- **Checks:**
  - Entry visibility is PUBLIC (from DEFAULT_VISIBILITY mapping)

### ST-7.10: Extraction emits events
- **Validates:** Fact extraction emits MEMORY_WRITE events for observability
- **Method:** Create FactExtractor with event_bus, run extraction
- **Checks:**
  - At least one MEMORY_WRITE event emitted
  - Event payload contains `source: auto_extract`

### ST-7.11: Auto-extract disabled
- **Validates:** `auto_extract=False` prevents extraction from running
- **Method:** Create agent with `auto_extract=False`, run with mocked LLM and mocked extractor
- **Checks:**
  - Extractor's `extract()` method is never called

### ST-7.12: Extraction failure safe
- **Validates:** Extraction failure does not break the agent run
- **Method:** Create agent with `auto_extract=True`, mock extractor raises RuntimeError
- **Checks:**
  - Agent run completes successfully
  - Response content is returned normally

### ST-7.13: Config summary_model
- **Validates:** `summary_model` field on AgentConfig
- **Method:** Create AgentConfig with and without summary_model
- **Checks:**
  - Explicit value is stored correctly
  - Default is None (falls back to platform config)

### ST-7.14: Config extraction_model
- **Validates:** `extraction_model` and `auto_extract` fields on AgentConfig
- **Method:** Create AgentConfig with extraction_model and auto_extract=True
- **Checks:**
  - Both fields stored correctly

### ST-7.15: Remember tool visibility
- **Validates:** `remember` tool accepts and persists visibility parameter
- **Method:** Call remember tool with `visibility: "public"` for a domain_knowledge entry
- **Checks:**
  - Tool call succeeds
  - Stored entry has PUBLIC visibility
