# V1 Phase 4 — Plan

## Phase Reference
- **Version:** V1
- **Phase:** 4
- **Title:** Memory System
- **Roadmap Section:** §4, V1 Phase 4

## Prerequisites
- V1 Phase 0–3 — COMPLETE

## Deliverables Checklist
- [ ] `MemoryEntry` model with `MemoryType` enum
- [ ] `ChromaMemoryStore` — ChromaDB-backed storage with built-in embedding and similarity search
- [ ] `EmbeddingProvider` stub for testing (deterministic fake vectors)
- [ ] Memory retrieval — semantic search via ChromaDB
- [ ] `TimeDecayStrategy` — logarithmic decay with access boost
- [ ] Memory as tools — `remember`, `recall`, `forget` exposed via ToolProvider
- [ ] `MemoryToolProvider` registered in ToolRegistry
- [ ] Context manager — assembles messages with memory injection
- [ ] Runtime integration — inject memories at start of each run
- [ ] Events emitted for all memory operations

## Implementation Steps

1. **MemoryEntry model and MemoryType enum**
   - `backend/src/agent_platform/memory/models.py`
   - Fields: id, agent_id, content, embedding, memory_type, importance, created_at, last_accessed_at, access_count, decay_score

2. **ChromaDB memory store**
   - `backend/src/agent_platform/memory/chroma_memory_store.py`
   - Uses ChromaDB persistent client with a single collection
   - Stores MemoryEntry fields as ChromaDB metadata
   - Similarity search via ChromaDB's built-in nearest-neighbor
   - Accepts an `EmbeddingFunction` (ChromaDB interface) for embedding
   - Filter by agent_id, memory_type via ChromaDB `where` clauses
   - CRUD: add, get, list, delete, search

3. **Fake embedding provider for testing**
   - `backend/src/agent_platform/memory/fake_embeddings.py`
   - Implements both `EmbeddingProvider` (our protocol) and ChromaDB's `EmbeddingFunction`
   - Returns deterministic vectors based on text hash (consistent, no API calls)

4. **TimeDecayStrategy**
   - `backend/src/agent_platform/memory/decay.py`
   - Logarithmic decay based on time since last access
   - Boosted by access_count and importance
   - Configurable half-life

5. **MemoryToolProvider**
   - `backend/src/agent_platform/memory/memory_tools.py`
   - Implements `ToolProvider` with three tools: `remember`, `recall`, `forget`
   - Uses ChromaMemoryStore + EmbeddingProvider internally

6. **Context manager**
   - `backend/src/agent_platform/memory/context_manager.py`
   - `assemble_context(agent, conversation, query)` — retrieves top-K relevant memories and injects them as a system message

7. **Wire into AgentRuntime**
   - Update runtime to call context manager before LLM calls
   - Register MemoryToolProvider in ToolRegistry
   - Emit MEMORY_READ/MEMORY_WRITE events

8. **Update app factory**
   - Wire ChromaMemoryStore, EmbeddingProvider, MemoryToolProvider, ContextManager

## Dependencies & Libraries

### New dependency
| Package | Version | Purpose |
|---------|---------|---------|
| chromadb | >=1.0 | Vector database for memory storage and similarity search |

ChromaDB runs in-process with persistent local storage. No external server needed. Cross-platform compatible.

## File Manifest

### New files
- `backend/src/agent_platform/memory/models.py` — MemoryEntry, MemoryType
- `backend/src/agent_platform/memory/chroma_memory_store.py` — ChromaDB memory store
- `backend/src/agent_platform/memory/fake_embeddings.py` — Test embedding provider
- `backend/src/agent_platform/memory/decay.py` — TimeDecayStrategy
- `backend/src/agent_platform/memory/memory_tools.py` — MemoryToolProvider
- `backend/src/agent_platform/memory/context_manager.py` — Context assembly
- `backend/tests/smoke/test_v1_phase_4.py` — Phase 4 smoke tests

### Modified files
- `backend/pyproject.toml` — add chromadb dependency
- `backend/src/agent_platform/core/runtime.py` — inject memories via context manager
- `backend/src/agent_platform/api/main.py` — wire memory components
- `backend/src/agent_platform/api/_deps.py` — add memory access

## Risks & Decisions

- **ChromaDB for vector storage:** Handles embeddings, similarity search, and metadata filtering natively. Runs in-process with persistent local storage — no external server. Can be swapped via the `VectorStore` abstraction later if needed.
- **Fake embeddings in tests:** All smoke tests use `FakeEmbeddingProvider` which returns deterministic vectors. No API calls. The fake provider implements both our `EmbeddingProvider` protocol and ChromaDB's `EmbeddingFunction` interface.
- **Memory injection is additive:** Context manager prepends a "Relevant memories" system message before the conversation. It doesn't compress or truncate existing messages yet — full context compression (TruncateAndSummarize) is left as enhancement since it requires LLM calls during assembly.
- **Backward compatibility:** Runtime and app factory changes are backward compatible — memory components are optional.
