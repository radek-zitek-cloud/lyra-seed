# V2 Phase 2 — Plan

## Phase Reference
- **Version:** V2
- **Phase:** 2
- **Title:** Inter-Agent Communication & Async Lifecycle
- **Roadmap Section:** §502-563

## Prerequisites
- [x] V2 Phase 1: Sub-Agent Spawning — COMPLETE

## Deliverables Checklist
- [ ] 2.1: AgentMessage model + MessageType enum + SqliteMessageRepo
- [ ] 2.2: Async sub-agent spawning (background tasks, immediate return)
- [ ] 2.3: Message passing tools (send_message, receive_messages, dismiss_agent)
- [ ] 2.4: Lifecycle tools (check_agent_status, stop_agent, async wait_for_agent)
- [ ] 2.5: Runtime GUIDANCE message injection in iteration loop
- [ ] 2.6: Message API endpoints (GET/POST)
- [ ] 2.7: Frontend MessagePanel + message observability in UI

## Implementation Steps

1. Add MessageType enum and AgentMessage model to core/models.py
2. Create SqliteMessageRepo following existing repo pattern
3. Refactor agent_spawner.py: async spawn with background tasks
4. Add new tools: check_agent_status, stop_agent, send_message, receive_messages, dismiss_agent
5. Update wait_for_agent to actually wait (asyncio.Event per child)
6. Modify runtime.py: check for GUIDANCE messages at start of each iteration
7. Create message_routes.py: GET/POST endpoints
8. Wire everything in main.py and _deps.py
9. Create MessagePanel.tsx component
10. Integrate messages into agent detail page

## File Manifest
- `backend/src/agent_platform/core/models.py` — add MessageType, AgentMessage
- `backend/src/agent_platform/db/sqlite_message_repo.py` — new
- `backend/src/agent_platform/tools/agent_spawner.py` — async spawn + new tools
- `backend/src/agent_platform/core/runtime.py` — GUIDANCE injection
- `backend/src/agent_platform/api/message_routes.py` — new
- `backend/src/agent_platform/api/main.py` — wiring
- `backend/src/agent_platform/api/_deps.py` — message_repo getter
- `frontend/src/components/MessagePanel.tsx` — new
- `frontend/src/app/agents/[id]/page.tsx` — messages panel
- `frontend/src/lib/api.ts` — message API helpers

## Risks & Decisions
- Async spawn requires careful shutdown cleanup (cancel background tasks)
- Message inbox check adds latency to each runtime iteration (mitigate: only query if agent has parent)
- Reusable lifecycle means idle children persist — may need cleanup policy later
