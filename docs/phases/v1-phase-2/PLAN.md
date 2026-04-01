# V1 Phase 2 — Plan

## Phase Reference
- **Version:** V1
- **Phase:** 2
- **Title:** Agent Runtime
- **Roadmap Section:** §4, V1 Phase 2

## Prerequisites
- V1 Phase 0 (Project Skeleton & Tooling) — COMPLETE
- V1 Phase 1 (Abstractions & Event System) — COMPLETE

## Deliverables Checklist
- [ ] Agent data model (`Agent`, `AgentStatus`, `AgentConfig`)
- [ ] Conversation model (reuses `Message` from Phase 1)
- [ ] SQLite repository for agents
- [ ] SQLite repository for conversations
- [ ] `OpenRouterProvider` implementation of `LLMProvider`
- [ ] `AgentRuntime` core loop with event emission
- [ ] Max-iterations safety guard
- [ ] HITL foundation (`HITLPolicy`, permission gate, HITL_REQUEST/RESPONSE events)
- [ ] API endpoints: create agent, send prompt, HITL respond
- [ ] `AgentResponse` model

## Implementation Steps

1. **Agent and conversation data models**
   - `backend/src/agent_platform/core/models.py` — `Agent`, `AgentStatus`, `AgentConfig`, `AgentResponse`, `Conversation`, `HITLPolicy`
   - Extends the existing `Message` model from `llm/models.py` (add `timestamp` field)

2. **SQLite repository for agents**
   - `backend/src/agent_platform/db/sqlite_agent_repo.py` — implements `Repository[Agent]`
   - Creates `agents` table, CRUD operations via aiosqlite

3. **SQLite repository for conversations**
   - `backend/src/agent_platform/db/sqlite_conversation_repo.py` — implements `Repository[Conversation]`
   - Creates `conversations` table with messages stored as JSON array

4. **OpenRouter LLM provider**
   - `backend/src/agent_platform/llm/openrouter.py` — implements `LLMProvider`
   - HTTP POST to OpenRouter API via httpx
   - Maps internal `Message`/`ToolCall`/`LLMResponse` to/from OpenRouter format
   - Emits LLM_REQUEST and LLM_RESPONSE events
   - Error handling with retries (exponential backoff)

5. **Agent runtime engine**
   - `backend/src/agent_platform/core/runtime.py` — `AgentRuntime` class
   - `run(agent_id, human_message) -> AgentResponse` method
   - Core loop: load agent → assemble context → LLM call → handle tool calls or return
   - `max_iterations` guard to prevent infinite loops
   - Emits events at every step (LLM_REQUEST, LLM_RESPONSE, TOOL_CALL, TOOL_RESULT, ERROR)

6. **HITL permission gate**
   - Integrated into `AgentRuntime` — checks `HITLPolicy` before tool execution
   - Emits HITL_REQUEST, waits for HITL_RESPONSE via event bus
   - `HITLGate` helper class for the wait/respond pattern

7. **API endpoints**
   - Add to `backend/src/agent_platform/api/main.py` or a separate router:
     - `POST /agents` — create a new agent
     - `POST /agents/{id}/prompt` — send a human message, run agent
     - `POST /agents/{id}/hitl-respond` — approve/deny a pending HITL gate
     - `GET /agents/{id}` — get agent details

## Dependencies & Libraries

No new runtime dependencies. All existing:
- `httpx` — HTTP client for OpenRouter API
- `aiosqlite` — async SQLite
- `pydantic` — data models
- `fastapi` — API endpoints

## File Manifest

### New files
- `backend/src/agent_platform/core/models.py` — Agent, AgentConfig, AgentStatus, Conversation, AgentResponse, HITLPolicy
- `backend/src/agent_platform/db/sqlite_agent_repo.py` — SQLite agent repository
- `backend/src/agent_platform/db/sqlite_conversation_repo.py` — SQLite conversation repository
- `backend/src/agent_platform/llm/openrouter.py` — OpenRouter LLM provider
- `backend/src/agent_platform/core/runtime.py` — AgentRuntime engine
- `backend/src/agent_platform/api/routes.py` — API routes (agents, prompt, HITL)
- `backend/tests/smoke/test_v1_phase_2.py` — Phase 2 smoke tests

### Modified files
- `backend/src/agent_platform/llm/models.py` — add optional `timestamp` to Message
- `backend/src/agent_platform/api/main.py` — register routes, wire dependencies

## Risks & Decisions

- **OpenRouter in smoke tests:** All LLM calls are mocked. The `OpenRouterProvider` is tested for correct request/response mapping using a mock HTTP transport, never hitting the real API.
- **Conversation storage:** Messages stored as a JSON array column in SQLite. Simple for Phase 2; can be normalized later if needed.
- **HITL in smoke tests:** The HITL gate is tested by emitting an HITL_RESPONSE event from the test itself, simulating a human approving/denying.
- **Tool execution in Phase 2:** The agent runtime supports tool call detection and loop structure, but actual tool execution is deferred to Phase 3 (Tool System). In Phase 2, unresolved tool calls return a stub "tool not available" result.
