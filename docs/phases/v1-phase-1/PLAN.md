# V1 Phase 1 — Plan

## Phase Reference
- **Version:** V1
- **Phase:** 1
- **Title:** Abstractions & Event System
- **Roadmap Section:** §4, V1 Phase 1

## Prerequisites
- V1 Phase 0 (Project Skeleton & Tooling) — COMPLETE

## Deliverables Checklist
- [ ] `LLMProvider` protocol + `LLMResponse` / `Message` models
- [ ] `EmbeddingProvider` protocol
- [ ] `Repository[T]` generic protocol
- [ ] `VectorStore` protocol + `VectorResult` model
- [ ] `Strategy[TInput, TOutput]` generic protocol
- [ ] `Event` Pydantic model + `EventType` enum
- [ ] `EventBus` protocol + `EventFilter` model
- [ ] `InProcessEventBus` implementation (in-memory queue + SQLite persistence)
- [ ] SQLite event persistence (create table, insert, query)
- [ ] Real-time event subscription via async iterator

## Implementation Steps

1. **Create LLM abstraction models and protocol**
   - `backend/src/agent_platform/llm/models.py` — `Message`, `ToolCall`, `LLMResponse`, `LLMConfig`
   - `backend/src/agent_platform/llm/provider.py` — `LLMProvider` protocol

2. **Create embedding abstraction**
   - `backend/src/agent_platform/llm/embeddings.py` — `EmbeddingProvider` protocol

3. **Create repository abstraction**
   - `backend/src/agent_platform/db/repository.py` — `Repository[T]` protocol, `Pagination`, `Filters`

4. **Create vector store abstraction**
   - `backend/src/agent_platform/db/vector_store.py` — `VectorStore` protocol, `VectorResult`

5. **Create strategy abstraction**
   - `backend/src/agent_platform/core/strategy.py` — `Strategy[TInput, TOutput]` protocol

6. **Create event models**
   - `backend/src/agent_platform/observation/events.py` — `Event` model, `EventType` enum, `EventFilter`

7. **Create EventBus protocol**
   - `backend/src/agent_platform/observation/event_bus.py` — `EventBus` protocol

8. **Create SQLite event store**
   - `backend/src/agent_platform/observation/sqlite_event_store.py` — creates `events` table, insert/query methods

9. **Create InProcessEventBus implementation**
   - `backend/src/agent_platform/observation/in_process_event_bus.py` — ties together in-memory async queue + SQLite persistence

10. **Wire EventBus into app factory**
    - Update `create_app()` to optionally accept and store an EventBus instance via `app.state`

## Dependencies & Libraries

No new dependencies needed. All abstractions use:
- `typing.Protocol` (stdlib)
- `pydantic` (already installed)
- `aiosqlite` (already installed)
- `asyncio` (stdlib)

## File Manifest

### New files
- `backend/src/agent_platform/llm/models.py` — LLM data models
- `backend/src/agent_platform/llm/provider.py` — LLMProvider protocol
- `backend/src/agent_platform/llm/embeddings.py` — EmbeddingProvider protocol
- `backend/src/agent_platform/db/repository.py` — Repository protocol
- `backend/src/agent_platform/db/vector_store.py` — VectorStore protocol
- `backend/src/agent_platform/core/strategy.py` — Strategy protocol
- `backend/src/agent_platform/observation/events.py` — Event model, EventType, EventFilter
- `backend/src/agent_platform/observation/event_bus.py` — EventBus protocol
- `backend/src/agent_platform/observation/sqlite_event_store.py` — SQLite persistence for events
- `backend/src/agent_platform/observation/in_process_event_bus.py` — InProcessEventBus implementation
- `backend/tests/smoke/test_v1_phase_1.py` — Phase 1 smoke tests

### Modified files
- `backend/src/agent_platform/api/main.py` — wire EventBus into app state

## Risks & Decisions

- **Protocol vs ABC:** Using `typing.Protocol` for structural subtyping (duck typing) rather than ABCs. This is more Pythonic and doesn't force inheritance.
- **SQLite for events:** Using aiosqlite directly rather than Alembic migrations for Phase 1. The events table schema is simple enough to create programmatically. Alembic can be introduced later.
- **Event payload as JSON:** The `payload` field is `dict[str, Any]` serialized as JSON text in SQLite. This keeps the schema simple while allowing arbitrary event data.
- **Subscriber model:** Using `asyncio.Queue` per subscriber. Each call to `subscribe()` creates a new queue that receives copies of emitted events. Subscribers must be consumed or cancelled to avoid memory leaks.
