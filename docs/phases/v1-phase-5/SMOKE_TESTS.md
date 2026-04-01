# V1 Phase 5 — Smoke Tests

## Test Environment
- Prerequisites: phases 0–4 complete, backend dependencies installed, frontend dependencies installed
- Platform: must pass on both Linux (bash) and Windows (PowerShell)
- LLM calls: always mocked
- External APIs: never called

## Backend Smoke Tests

### ST-5.1: List agents endpoint
- **Validates:** `GET /agents` returns all agents
- **Method:** Create two agents via API, then GET /agents
- **Checks:**
  - Returns 200 with a JSON array
  - Array contains both created agents
  - Each agent has id, name, status fields

### ST-5.2: Agent events endpoint
- **Validates:** `GET /agents/{id}/events` returns filtered events
- **Method:** Create agent, trigger events by running the agent (mocked LLM), then query events
- **Checks:**
  - Returns 200 with a JSON array of events
  - Events have correct agent_id
  - Supports event_type query parameter filtering

### ST-5.3: Agent conversations endpoint
- **Validates:** `GET /agents/{id}/conversations` returns conversation history
- **Method:** Create agent, send a prompt (mocked LLM), then query conversations
- **Checks:**
  - Returns 200 with conversation data
  - Conversation contains messages with roles and content

### ST-5.4: Tools list endpoint
- **Validates:** `GET /tools` returns registered tools
- **Method:** Register a macro tool, then GET /tools
- **Checks:**
  - Returns 200 with a JSON array
  - Contains registered tool with name, description, tool_type

### ST-5.5: Tool calls history endpoint
- **Validates:** `GET /tools/{name}/calls` returns tool call events
- **Method:** Create agent, run with mocked LLM that triggers tool call, query tool calls
- **Checks:**
  - Returns 200 with a JSON array of tool call events
  - Events contain tool name in payload

### ST-5.6: WebSocket agent event stream
- **Validates:** `WS /agents/{id}/events/stream` streams real-time events
- **Method:** Connect WebSocket, emit an event, verify it arrives
- **Checks:**
  - WebSocket connection established successfully
  - Events arrive as JSON messages
  - Events match the subscribed agent_id

### ST-5.7: WebSocket global event stream
- **Validates:** `WS /events/stream` streams all events
- **Method:** Connect WebSocket, emit events for different agents, verify all arrive
- **Checks:**
  - WebSocket connection established successfully
  - Events from multiple agents arrive

### ST-5.8: CORS headers present
- **Validates:** CORS middleware is configured
- **Method:** Send OPTIONS request with Origin header
- **Checks:**
  - Response includes Access-Control-Allow-Origin header
  - Response includes Access-Control-Allow-Methods header

## Frontend Smoke Tests

### ST-5.9: Agent list page renders
- **Validates:** Home page renders agent list
- **Method:** Render page component with mocked API data
- **Checks:**
  - Page renders without errors
  - Agent names are displayed
  - Status badges are visible

### ST-5.10: Agent detail page renders
- **Validates:** Agent detail page renders with conversation and events
- **Method:** Render agent detail component with mocked data
- **Checks:**
  - Agent name and status displayed
  - Conversation messages rendered
  - Event timeline rendered

### ST-5.11: HITL panel renders with pending actions
- **Validates:** HITL panel shows pending approvals
- **Method:** Render HITL panel with mocked pending HITL events
- **Checks:**
  - Pending approval items displayed
  - Approve and Deny buttons present

### ST-5.12: Tool inspector renders
- **Validates:** Tool inspector shows tool call history
- **Method:** Render tool inspector with mocked tool call events
- **Checks:**
  - Tool calls listed with name and status
  - Expandable details available
