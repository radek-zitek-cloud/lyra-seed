# V1 Phase 1 — Smoke Tests

## Test Environment
- Prerequisites: V1 Phase 0 complete, `uv` installed
- Platform: must pass on both Linux (bash) and Windows (PowerShell)
- Run: `cd backend && uv run pytest tests/smoke/ -k "v1_phase_1" -v --tb=short`

## ST-1.1: LLM provider protocol is defined
- **Validates:** LLMProvider protocol and associated models exist and are well-formed
- **Method:** Import types, verify protocol has required methods, instantiate models
- **Checks:**
  - `LLMProvider` protocol has `complete` method
  - `LLMResponse` model can be instantiated with content, tool_calls, usage
  - `Message` model can be instantiated with role and content

## ST-1.2: Embedding provider protocol is defined
- **Validates:** EmbeddingProvider protocol exists
- **Method:** Import and verify protocol shape
- **Checks:**
  - `EmbeddingProvider` protocol has `embed` and `embed_query` methods

## ST-1.3: Repository protocol is defined
- **Validates:** Generic repository protocol exists
- **Method:** Import and verify protocol shape
- **Checks:**
  - `Repository` protocol has `get`, `list`, `create`, `update`, `delete` methods

## ST-1.4: VectorStore protocol is defined
- **Validates:** VectorStore protocol and VectorResult model exist
- **Method:** Import and verify protocol shape, instantiate VectorResult
- **Checks:**
  - `VectorStore` protocol has `store`, `search`, `delete` methods
  - `VectorResult` model can be instantiated

## ST-1.5: Strategy protocol is defined
- **Validates:** Generic strategy protocol exists
- **Method:** Import and verify protocol shape
- **Checks:**
  - `Strategy` protocol has `execute` method

## ST-1.6: Event model and types are defined
- **Validates:** Event model, EventType enum, and EventFilter exist
- **Method:** Import types, instantiate Event, iterate EventType values
- **Checks:**
  - `EventType` enum has at least: LLM_REQUEST, LLM_RESPONSE, TOOL_CALL, TOOL_RESULT, ERROR
  - `Event` can be instantiated with required fields (auto-generates id/timestamp)
  - `EventFilter` can be instantiated with optional filter fields
  - Event `payload` field accepts arbitrary dict

## ST-1.7: Events can be emitted and received by subscribers
- **Validates:** InProcessEventBus emit + subscribe work together
- **Method:** Create bus, subscribe, emit event, receive from subscription
- **Checks:**
  - Emitted event is received by subscriber
  - Subscriber with event_type filter only receives matching events
  - Subscriber with agent_id filter only receives matching events
  - Multiple subscribers each receive the same event

## ST-1.8: Events persist to SQLite and can be queried
- **Validates:** SQLite event persistence and query
- **Method:** Create bus with temp SQLite db, emit events, query them back
- **Checks:**
  - Emitted event can be queried back from SQLite by agent_id
  - Events can be filtered by event_type
  - Events can be filtered by time range
  - Event payload roundtrips through JSON serialization correctly

## ST-1.9: EventBus is accessible from the FastAPI app
- **Validates:** EventBus is wired into the app factory
- **Method:** Create app, verify event bus is available on app state
- **Checks:**
  - `app.state.event_bus` is set and is an EventBus instance
