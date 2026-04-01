# V1 Phase 2 — Smoke Tests

## Test Environment
- Prerequisites: V1 Phase 0 + Phase 1 complete, `uv` installed
- Platform: must pass on both Linux (bash) and Windows (PowerShell)
- All LLM calls are mocked — no real API calls
- Run: `cd backend && uv run pytest tests/smoke/ -k "v1_phase_2" -v --tb=short`

## ST-2.1: Agent data model
- **Validates:** Agent, AgentStatus, AgentConfig, Conversation models
- **Method:** Import and instantiate models
- **Checks:**
  - `Agent` can be created with name, config; auto-generates id, timestamps
  - `AgentStatus` enum has IDLE, RUNNING, WAITING_HITL, COMPLETED, FAILED
  - `AgentConfig` has model, temperature, max_iterations, system_prompt
  - `Conversation` can hold a list of Messages

## ST-2.2: Agent SQLite repository CRUD
- **Validates:** SQLite agent repository implements full CRUD
- **Method:** Create temp DB, perform CRUD operations
- **Checks:**
  - `create` stores and returns an agent
  - `get` retrieves an agent by ID
  - `update` modifies agent fields
  - `delete` removes an agent
  - `list` returns all agents

## ST-2.3: Conversation SQLite repository
- **Validates:** Conversation persistence with message serialization
- **Method:** Create temp DB, store and retrieve conversations
- **Checks:**
  - Create a conversation with messages
  - Retrieve it — messages roundtrip correctly (role, content, tool_calls)
  - Update conversation with new messages

## ST-2.4: OpenRouter provider request/response mapping
- **Validates:** OpenRouterProvider correctly maps to/from OpenRouter API format
- **Method:** Mock httpx transport, send a completion request, verify mapping
- **Checks:**
  - Request maps Messages to OpenRouter format (role, content)
  - Response maps back to LLMResponse (content, tool_calls, usage)
  - Emits LLM_REQUEST and LLM_RESPONSE events

## ST-2.5: Agent runtime core loop (text response)
- **Validates:** Agent can receive a prompt and return a text response
- **Method:** Create agent with mock LLM provider, run with a prompt
- **Checks:**
  - Runtime loads agent, calls LLM, returns AgentResponse with content
  - Agent status transitions: IDLE → RUNNING → IDLE
  - Events emitted: at least LLM_REQUEST and LLM_RESPONSE

## ST-2.6: Agent runtime tool call loop
- **Validates:** Runtime handles tool calls in a loop
- **Method:** Mock LLM to return tool call first, then text response
- **Checks:**
  - Runtime detects tool calls in LLM response
  - Appends tool results and calls LLM again
  - Returns final text response after tool loop resolves
  - TOOL_CALL and TOOL_RESULT events emitted

## ST-2.7: Max iterations guard
- **Validates:** Runtime stops after max_iterations to prevent infinite loops
- **Method:** Mock LLM to always return tool calls, set max_iterations=2
- **Checks:**
  - Runtime stops after 2 iterations
  - Agent status set to FAILED or response indicates limit reached
  - ERROR event emitted

## ST-2.8: HITL permission gate
- **Validates:** HITL gate pauses execution and resumes on response
- **Method:** Configure agent with HITL policy ALWAYS_ASK, mock a tool call
- **Checks:**
  - Runtime emits HITL_REQUEST when tool call requires approval
  - Agent status → WAITING_HITL
  - After HITL_RESPONSE (approve), execution continues
  - After HITL_RESPONSE (deny), tool call is skipped

## ST-2.9: API endpoints
- **Validates:** REST endpoints for agent management
- **Method:** httpx AsyncClient with test app
- **Checks:**
  - `POST /agents` creates an agent, returns 201 with agent data
  - `GET /agents/{id}` returns agent details
  - `POST /agents/{id}/prompt` accepts a message (mocked LLM)
  - `POST /agents/{id}/hitl-respond` accepts approve/deny
