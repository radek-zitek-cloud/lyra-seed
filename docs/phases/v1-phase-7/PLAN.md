# V1 Phase 7 — Plan

## Phase Reference
- **Version:** V1
- **Phase:** 7
- **Title:** Memory Enhancement
- **Scope:** Context summarization (replaces truncation), automatic fact extraction, cross-agent memory with visibility model

## Prerequisites
- [x] V1 Phase 0: Project Skeleton & Tooling — COMPLETE
- [x] V1 Phase 1: Abstractions & Event System — COMPLETE
- [x] V1 Phase 2: Agent Runtime — COMPLETE
- [x] V1 Phase 3: Tool System — COMPLETE
- [x] V1 Phase 4: Memory System — COMPLETE
- [x] V1 Phase 5: Observation UI — COMPLETE
- [x] V1 Phase 6: Pre-V2 Hardening — COMPLETE

## Deliverables Checklist

### 7.1 — Cross-Agent Memory with Visibility Model
- [x] `MemoryVisibility` enum: PRIVATE, TEAM, PUBLIC, INHERIT
- [x] `MemoryEntry.visibility` field (default PRIVATE, backward compatible)
- [x] Default visibility by memory type — PUBLIC for shared knowledge (FACT, PROCEDURE, TOOL_KNOWLEDGE, DOMAIN_KNOWLEDGE), PRIVATE for agent-specific (EPISODIC, PREFERENCE, DECISION, OUTCOME)
- [x] `ChromaMemoryStore.search(include_public=True)` uses ChromaDB `$or` filter
- [x] `remember` tool accepts explicit `visibility` parameter
- [x] `recall` tool defaults to `include_public=True`
- [x] Context injection marks non-owner memories as `[shared]`

### 7.2 — Context Summarization (Replaces Truncation)
- [x] `ContextSummarizer` calls LLM to summarize dropped messages
- [x] Summary saved as EPISODIC memory (importance=0.6, visibility=PRIVATE)
- [x] Summary marker injected: `[Summary of N earlier messages: ...]`
- [x] Fallback to truncation marker if no LLM provider configured
- [x] Configurable `summaryModel` per agent
- [x] System prompt loaded from `prompts/system/summarize.md`
- [x] MEMORY_WRITE event emitted with `source: context_summarization`

### 7.3 — Automatic Fact Extraction
- [x] `FactExtractor` extracts facts/preferences/decisions after each agent turn
- [x] Runs after final response when `auto_extract=True`
- [x] Sends last 6 messages + response to extraction LLM
- [x] LLM returns JSON array: `[{content, memory_type, importance}]`
- [x] Extracted items stored as MemoryEntry with visibility from `memory_sharing` config
- [x] MEMORY_WRITE events emitted with `source: auto_extract`
- [x] Failures caught silently — extraction never breaks the agent run
- [x] Configurable `extractionModel` per agent
- [x] System prompt loaded from `prompts/system/extract_facts.md`
- [x] Toggleable per agent via `auto_extract: bool` in config

### 7.4 — Externalized System Prompts
- [x] Summarization and extraction prompts stored as `prompts/system/*.md` files
- [x] `load_system_prompt(name, project_root)` helper in platform_config
- [x] Loaded once on startup, passed to summarizer and extractor at construction
- [x] Version-controllable, editable without touching Python code

### 7.5 — Configuration
- [x] `summary_model` in AgentConfig (falls back to platform `summaryModel`)
- [x] `extraction_model` in AgentConfig (falls back to platform `extractionModel`)
- [x] `auto_extract: bool` in AgentConfig (default from file config)
- [x] `memory_sharing: dict` in AgentConfig (maps memory_type → visibility)
- [x] All follow the 4-level resolution chain: agent.json → default.json → lyra.config.json → hardcoded

## Implementation Steps

### Step 1: Visibility model
- Add `MemoryVisibility` enum and `visibility` field to `MemoryEntry`
- Define `DEFAULT_VISIBILITY` mapping (type → visibility)
- Update `ChromaMemoryStore` to store/filter visibility metadata
- Update `search()` with `include_public` using ChromaDB `$or` filter
- Update `remember` tool to accept `visibility` parameter
- Update `recall` tool to default to `include_public=True`
- Update `ContextManager.assemble()` to mark shared memories with `[shared]` prefix
- **Files:** `memory/models.py`, `memory/chroma_memory_store.py`, `memory/memory_tools.py`, `memory/context_manager.py`

### Step 2: Context summarization
- Create `memory/summarizer.py` with `ContextSummarizer`
- Create `prompts/system/summarize.md` with summarization prompt
- Update `ContextManager._compress()` to call summarizer instead of simple truncation
- Save summary as EPISODIC memory in ChromaDB
- Emit MEMORY_WRITE event for observability
- **Files:** `memory/summarizer.py` (new), `prompts/system/summarize.md` (new), `memory/context_manager.py`

### Step 3: Automatic fact extraction
- Create `memory/extractor.py` with `FactExtractor`
- Create `prompts/system/extract_facts.md` with extraction prompt
- Wire extraction into runtime: call after final LLM response when `auto_extract=True`
- **Files:** `memory/extractor.py` (new), `prompts/system/extract_facts.md` (new), `core/runtime.py`

### Step 4: Configuration wiring
- Add `summary_model`, `extraction_model`, `auto_extract`, `memory_sharing` to `AgentConfig`
- Add resolution in `platform_config.py` and `file_config.py`
- Load system prompts from `prompts/system/` on startup
- Wire summarizer and extractor into app factory
- **Files:** `core/models.py`, `core/platform_config.py`, `api/main.py`, `api/routes.py`

## File Manifest

### New Files
- `backend/src/agent_platform/memory/summarizer.py` — LLM-based context summarization
- `backend/src/agent_platform/memory/extractor.py` — automatic fact extraction
- `prompts/system/summarize.md` — summarization system prompt
- `prompts/system/extract_facts.md` — extraction system prompt
- `backend/tests/smoke/test_v1_phase_7.py` — 15 smoke tests

### Modified Files
- `backend/src/agent_platform/memory/models.py` — MemoryVisibility enum, DEFAULT_VISIBILITY, visibility field
- `backend/src/agent_platform/memory/chroma_memory_store.py` — visibility metadata, $or filter, get() method
- `backend/src/agent_platform/memory/memory_tools.py` — visibility parameter on remember, include_public on recall
- `backend/src/agent_platform/memory/context_manager.py` — LLM summarization, [shared] prefix, event emission
- `backend/src/agent_platform/core/models.py` — summary_model, extraction_model, auto_extract, memory_sharing fields
- `backend/src/agent_platform/core/runtime.py` — _auto_extract() call, extractor wiring
- `backend/src/agent_platform/core/platform_config.py` — load_system_prompt(), summaryModel/extractionModel resolution
- `backend/src/agent_platform/api/main.py` — construct and wire summarizer/extractor
- `backend/src/agent_platform/api/routes.py` — resolve new config fields from file config
- `prompts/default.json` — add auto_extract, memory_sharing, summary_model, extraction_model defaults

## Risks & Decisions
- **Summarization uses cheap model:** Defaults to `gpt-5.4-nano` / `gpt-4.1-nano` to keep costs low for automated summarization.
- **Extraction is best-effort:** Failures are caught and logged; never break the agent run. Quality depends on the extraction model.
- **TEAM resolves to PUBLIC:** Until V2 adds parent-child agent hierarchy, TEAM visibility is treated as PUBLIC.
- **INHERIT reserved for V2:** Not yet implemented; exists in the enum for forward compatibility.
- **Backward compatibility:** Existing memories without visibility metadata default to PRIVATE, preserving pre-Phase 7 behavior.
