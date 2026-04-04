# V4 Phase 2 — Plan

## Phase Reference
- **Version:** V4
- **Phase:** 2
- **Title:** RAG Knowledge Base
- **Roadmap Section:** POST_V3_ROADMAP.md V4P2

## Prerequisites
- [x] V4 Phase 1: Technical Alignment & Cleanup — COMPLETE

## Deliverables Checklist
- [ ] 2.1: `KnowledgeStore` — ChromaDB-backed store for document chunks (separate collection from memories)
- [ ] 2.2: Document chunker — heading-aware markdown splitter
- [ ] 2.3: `search_knowledge(query, top_k)` tool — semantic search over the knowledge base
- [ ] 2.4: `ingest_document(path)` tool — agent adds a document at runtime
- [ ] 2.5: Directory scanning — load all `.md` files from `knowledge/` at startup
- [ ] 2.6: `knowledgeDir` in PlatformConfig
- [ ] 2.7: Hot-reload — `/config/reload` re-indexes changed documents
- [ ] 2.8: Integration with `analyze_capabilities` — includes relevant knowledge in gap analysis
- [ ] 2.9: Update system prompt

## Implementation Steps

### 1. Document chunker
**Files:** `backend/src/agent_platform/knowledge/chunker.py`

- Split `.md` files into chunks by headings (##, ###)
- Each chunk retains: source file, heading path (e.g., "Memory > Context Manager"), chunk text
- Chunks are 200-1000 tokens — split large sections, keep small ones whole
- Returns list of `DocumentChunk` objects

### 2. KnowledgeStore
**Files:** `backend/src/agent_platform/knowledge/store.py`

- Uses a separate ChromaDB collection (`knowledge_base`, distinct from `memories`)
- Same `PersistentClient` as memory store (shared persist dir)
- `ingest(path)` — reads file, chunks, embeds, stores with metadata (source, heading)
- `search(query, top_k)` — semantic search returning chunks with source attribution
- `ingest_directory(dir_path)` — batch ingest all `.md` files
- `get_sources()` — list all ingested documents
- Dedup by source+heading — re-ingesting a file replaces its chunks

### 3. search_knowledge tool
**Files:** `backend/src/agent_platform/knowledge/tools.py`

- `search_knowledge(query, top_k=5)` tool
- Returns chunks with: content, source file, heading path, relevance score
- Agent can use results to ground its responses in documented knowledge

### 4. ingest_document tool
**Files:** `backend/src/agent_platform/knowledge/tools.py`

- `ingest_document(path)` tool
- Reads file from filesystem, chunks, embeds, stores
- Returns count of chunks indexed
- Validates file exists and is `.md`

### 5. KnowledgeToolProvider
**Files:** `backend/src/agent_platform/knowledge/tools.py`

- Implements `ToolProvider` protocol
- Registers `search_knowledge` and `ingest_document` tools

### 6. Wire into main.py
**Files:** `backend/src/agent_platform/api/main.py`

- Create KnowledgeStore with same ChromaDB persist dir
- Create KnowledgeToolProvider, register with ToolRegistry
- Scan `knowledgeDir` at startup and ingest all `.md` files
- Add `knowledgeDir` to PlatformConfig (default `./knowledge`)

### 7. Hot-reload
**Files:** `backend/src/agent_platform/api/config_routes.py`

- `/config/reload` re-indexes knowledge directory

### 8. analyze_capabilities integration
**Files:** `backend/src/agent_platform/tools/capability_tools.py`

- `_analyze` calls `knowledge_store.search(task)` and includes results in the report

### 9. System prompt
**Files:** `prompts/default.md`

- Document `search_knowledge` and `ingest_document`
- Guidance: search knowledge before answering questions that might have documented answers

## File Manifest
**New:**
- `backend/src/agent_platform/knowledge/__init__.py`
- `backend/src/agent_platform/knowledge/chunker.py` — markdown chunker
- `backend/src/agent_platform/knowledge/store.py` — KnowledgeStore
- `backend/src/agent_platform/knowledge/tools.py` — KnowledgeToolProvider
- `knowledge/` — directory for knowledge base files
- `backend/tests/smoke/test_v4_phase_2.py`

**Modified:**
- `backend/src/agent_platform/api/main.py` — wire knowledge store
- `backend/src/agent_platform/core/platform_config.py` — add knowledgeDir
- `backend/src/agent_platform/api/config_routes.py` — reload support
- `backend/src/agent_platform/tools/capability_tools.py` — knowledge in analyze
- `prompts/default.md` — document tools

## Risks & Decisions
- Separate ChromaDB collection for knowledge (not mixed with memories) — cleaner separation, independent lifecycle
- Chunking by markdown headings — simple, works well for structured docs. Not optimal for unstructured text.
- Re-ingesting a file replaces all its chunks — simpler than diffing
- Knowledge directory scanned at startup — acceptable for small-medium knowledge bases (tens of files, not thousands)
