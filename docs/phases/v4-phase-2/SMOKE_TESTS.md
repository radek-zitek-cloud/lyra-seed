# V4 Phase 2 — Smoke Tests

## Test Environment
- Prerequisites: V4P1 complete, all prior smoke tests passing
- LLM calls: always mocked
- Embedding calls: mocked with deterministic fake vectors
- External APIs: never called

## Backend Smoke Tests

### ST-V4-2.1: Markdown chunker splits by headings
- **Validates:** Document chunking
- **Method:** Create a markdown file with multiple headings, chunk it
- **Checks:**
  - Each heading creates a new chunk
  - Chunk metadata includes source file and heading path
  - Content is preserved correctly
  - Nested headings create hierarchical heading paths

### ST-V4-2.2: KnowledgeStore ingests and searches
- **Validates:** Store lifecycle
- **Method:** Ingest a test document, search for content
- **Checks:**
  - Document chunks stored in ChromaDB
  - Search returns relevant chunks with source attribution
  - Search ranks by relevance

### ST-V4-2.3: Re-ingesting replaces chunks
- **Validates:** Dedup on re-ingest
- **Method:** Ingest a file, modify it, re-ingest
- **Checks:**
  - Old chunks removed
  - New chunks stored
  - Search returns updated content

### ST-V4-2.4: search_knowledge tool returns results
- **Validates:** Tool integration
- **Method:** Ingest document, call search_knowledge tool
- **Checks:**
  - Returns chunks with content, source, heading
  - Results are valid JSON

### ST-V4-2.5: ingest_document tool indexes a file
- **Validates:** Runtime ingestion
- **Method:** Call ingest_document with a file path
- **Checks:**
  - File chunks stored
  - Returns chunk count
  - Rejects non-.md files
  - Rejects nonexistent files

### ST-V4-2.6: Directory scanning at startup
- **Validates:** Batch ingestion
- **Method:** Create knowledge dir with files, init store
- **Checks:**
  - All .md files in directory ingested
  - get_sources returns all file names

### ST-V4-2.7: PlatformConfig has knowledgeDir
- **Validates:** Config field
- **Checks:**
  - Default is "./knowledge"
  - Configurable

### ST-V4-2.8: App integration — tools registered
- **Validates:** Wiring
- **Method:** Create app, check tools
- **Checks:**
  - search_knowledge appears in GET /tools
  - ingest_document appears in GET /tools

### ST-V4-2.9: analyze_capabilities includes knowledge
- **Validates:** Integration with capability analysis
- **Method:** Ingest document, call analyze_capabilities
- **Checks:**
  - Report includes relevant_knowledge field with matching chunks
