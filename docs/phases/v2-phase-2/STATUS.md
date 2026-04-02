# V2 Phase 2 — COMPLETE

## Current State
- Started: 2026-04-02
- Last updated: 2026-04-02
- Completed: 2026-04-02

## Smoke Test Results
| ID | Description | Status | Notes |
|----|-------------|--------|-------|
| ST-V2-2.1 | AgentMessage model | PASS | |
| ST-V2-2.2 | Message repo CRUD | PASS | |
| ST-V2-2.3 | Async spawn returns immediately | PASS | |
| ST-V2-2.4 | Child runs in background | PASS | |
| ST-V2-2.5 | wait_for_agent blocks | PASS | |
| ST-V2-2.6 | check_agent_status | PASS | |
| ST-V2-2.7 | stop_agent | PASS | |
| ST-V2-2.8 | send_message + events | PASS | |
| ST-V2-2.9 | receive_messages | PASS | |
| ST-V2-2.10 | dismiss_agent | PASS | |
| ST-V2-2.11 | GUIDANCE injection | PASS | |
| ST-V2-2.12 | Message API GET | PASS | |
| ST-V2-2.13 | Message API POST | PASS | |
| ST-V2-2.14 | Reusable lifecycle | PASS | |
| ST-V2-2.15 | MessagePanel renders | PASS | |
| ST-V2-2.16 | MessagePanel send | PASS | |

## Regression Tests
- 98 backend smoke tests pass (all phases V1P0-V1P7, V2P1, V2P2)
- 6 frontend smoke tests pass (V1P5 + V2P2)
- V2P1 tests updated for async spawn behavior

## Iteration Log
### Iteration 1
- Created AgentMessage model + MessageType enum + SqliteMessageRepo
- Refactored agent_spawner: async spawn via background tasks
- Added tools: check_agent_status, stop_agent, send_message, receive_messages, dismiss_agent
- Updated wait_for_agent with asyncio.Event-based waiting
- Added runtime GUIDANCE injection (checks inbox each iteration)
- Created message API routes (GET/POST)
- Built MessagePanel frontend component
- Fixed V2P1 test regressions (3 tests assumed sync spawn)
- All 98+6 tests pass

## Decisions Made
- Messages stored in shared lyra.db (same as agents, conversations, events)
- GUIDANCE messages deleted after injection (consumed once)
- Spawn returns {"status": "running"} immediately
- Background tasks tracked in dict, cancelled on shutdown
- MessagePanel always visible in agent detail (not conditional on messages existing)
