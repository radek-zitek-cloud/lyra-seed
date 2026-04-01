# V1 Phase 5 — Plan

## Phase Reference
- **Version:** V1
- **Phase:** 5
- **Title:** Observation UI
- **Roadmap Section:** §4, V1 Phase 5

## Prerequisites
- [x] V1 Phase 0: Project Skeleton & Tooling — COMPLETE
- [x] V1 Phase 1: Abstractions & Event System — COMPLETE
- [x] V1 Phase 2: Agent Runtime — COMPLETE
- [x] V1 Phase 3: Tool System — COMPLETE
- [x] V1 Phase 4: Memory System — COMPLETE

## Deliverables Checklist

### 5.1 — Backend API for Observation
- [ ] `GET /agents` — list all agents
- [ ] `GET /agents/{id}/events` — query events with filters (type, time range, module)
- [ ] `GET /agents/{id}/conversations` — conversation history
- [ ] `GET /tools` — list all registered tools
- [ ] `GET /tools/{name}/calls` — history of calls to a specific tool
- [ ] `WS /agents/{id}/events/stream` — real-time event stream for an agent
- [ ] `WS /events/stream` — global event stream (all agents)
- [ ] CORS configuration for frontend-backend communication

### 5.2 — Observation UI: Agent View
- [ ] Agent list page with status badges
- [ ] Agent detail page with header, status, config summary
- [ ] Conversation panel (chat-style human ↔ agent messages)
- [ ] Event timeline (chronological, filterable, color-coded, expandable)
- [ ] Input bar to send prompts to the agent

### 5.3 — Observation UI: Tool Inspector
- [ ] Tool calls panel showing invocations with timestamp, tool name, duration
- [ ] Expandable input/output details
- [ ] Status indicator (success/failure)

### 5.4 — Observation UI: HITL Panel
- [ ] Pending approvals queue
- [ ] Approve/Deny buttons with optional message
- [ ] HITL history log

### 5.5 — Real-Time Updates
- [ ] WebSocket integration in frontend
- [ ] Live event timeline updates
- [ ] Agent status change reflection
- [ ] Connection status indicator

## Implementation Steps

### Step 1: Backend — Add missing REST endpoints
- Add `GET /agents` (list all) to `routes.py`
- Add `GET /agents/{id}/events` with query params for event_type, time_from, time_to, module
- Add `GET /agents/{id}/conversations` to return conversation history
- Add `GET /tools` to list all registered tools
- Add `GET /tools/{name}/calls` to query TOOL_CALL events filtered by tool name
- Add CORS middleware for frontend access
- **Files:** `backend/src/agent_platform/api/routes.py`, `backend/src/agent_platform/api/observation_routes.py`, `backend/src/agent_platform/api/main.py`

### Step 2: Backend — WebSocket endpoints
- Add `WS /agents/{id}/events/stream` using `event_bus.subscribe(agent_id=id)`
- Add `WS /events/stream` using `event_bus.subscribe()` (global)
- Both endpoints stream events as JSON over WebSocket
- Handle connection lifecycle (connect, disconnect, cleanup)
- **Files:** `backend/src/agent_platform/api/ws_routes.py`, `backend/src/agent_platform/api/main.py`

### Step 3: Frontend — Setup and dependencies
- Install UI dependencies: Tailwind CSS for styling
- Set up API client layer with fetch/WebSocket helpers
- Configure Next.js for backend API proxy
- **Files:** `frontend/package.json`, `frontend/src/lib/api.ts`, `frontend/tailwind.config.ts`, `frontend/postcss.config.mjs`

### Step 4: Frontend — Agent list page
- Create agent list page at `/` showing all agents with status badges
- Add navigation layout with header
- **Files:** `frontend/src/app/page.tsx`, `frontend/src/app/layout.tsx`, `frontend/src/components/AgentCard.tsx`

### Step 5: Frontend — Agent detail page
- Agent detail page at `/agents/[id]`
- Conversation panel showing messages
- Event timeline with filtering and expansion
- Prompt input bar
- **Files:** `frontend/src/app/agents/[id]/page.tsx`, `frontend/src/components/EventTimeline.tsx`, `frontend/src/components/ConversationPanel.tsx`, `frontend/src/components/PromptInput.tsx`

### Step 6: Frontend — Tool inspector
- Tool calls panel within agent detail view
- Shows tool invocations with details
- **Files:** `frontend/src/components/ToolInspector.tsx`

### Step 7: Frontend — HITL panel
- Pending approvals panel
- Approve/deny UI with message field
- **Files:** `frontend/src/components/HITLPanel.tsx`

### Step 8: Frontend — Real-time updates
- WebSocket hook for event streaming
- Live updates to event timeline and agent status
- Connection status indicator
- **Files:** `frontend/src/hooks/useEventStream.ts`, `frontend/src/components/ConnectionStatus.tsx`

### Step 9: Frontend — Test setup
- Install Vitest and React Testing Library
- Configure test environment
- **Files:** `frontend/package.json`, `frontend/vitest.config.ts`, `frontend/tests/smoke/smoke.v1-phase-5.spec.tsx`

## Dependencies & Libraries

### Backend (no new dependencies)
- FastAPI (existing) — includes WebSocket support natively
- All other deps already present

### Frontend (new)
- `tailwindcss`, `@tailwindcss/postcss`, `postcss` — styling
- `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom` — testing

## File Manifest

### Backend (new/modified)
- `backend/src/agent_platform/api/observation_routes.py` — new: observation REST endpoints
- `backend/src/agent_platform/api/ws_routes.py` — new: WebSocket endpoints
- `backend/src/agent_platform/api/routes.py` — modified: add GET /agents list
- `backend/src/agent_platform/api/main.py` — modified: include new routers, CORS
- `backend/tests/smoke/test_v1_phase_5.py` — new: smoke tests

### Frontend (new/modified)
- `frontend/src/lib/api.ts` — new: API client
- `frontend/src/app/page.tsx` — modified: agent list page
- `frontend/src/app/layout.tsx` — modified: navigation layout
- `frontend/src/app/agents/[id]/page.tsx` — new: agent detail page
- `frontend/src/components/AgentCard.tsx` — new: agent list card
- `frontend/src/components/EventTimeline.tsx` — new: event timeline
- `frontend/src/components/ConversationPanel.tsx` — new: conversation panel
- `frontend/src/components/PromptInput.tsx` — new: prompt input bar
- `frontend/src/components/ToolInspector.tsx` — new: tool calls panel
- `frontend/src/components/HITLPanel.tsx` — new: HITL panel
- `frontend/src/components/ConnectionStatus.tsx` — new: WS status
- `frontend/src/hooks/useEventStream.ts` — new: WebSocket hook
- `frontend/tailwind.config.ts` — new: Tailwind config
- `frontend/postcss.config.mjs` — new: PostCSS config
- `frontend/vitest.config.ts` — new: Vitest config
- `frontend/tests/smoke/smoke.v1-phase-5.spec.tsx` — new: frontend smoke tests

## Risks & Decisions
- **WebSocket in tests:** Backend WebSocket tests will use httpx WebSocket test client. Frontend WebSocket tests will mock the WebSocket connection.
- **Tailwind CSS:** Using Tailwind for rapid UI development. No component library needed for MVP.
- **Frontend smoke tests:** Will test component rendering with mocked API data, not end-to-end browser tests. This keeps them fast and reliable.
- **CORS:** Will allow localhost origins for development. Configuration via settings.
