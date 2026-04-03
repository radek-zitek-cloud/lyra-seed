# Agent-Drive Testing

This directory contains use case definitions and execution reports for API-driven testing of the Lyra Agent Platform. Claude Code acts as the test driver, substituting for a human user by calling the platform's REST API directly.

## How it works

Instead of manually testing through the web UI, Claude Code drives the platform programmatically:

1. **Create agents** via `POST /agents` with specific names/templates
2. **Send prompts** via `POST /agents/{id}/prompt` to trigger the agent runtime
3. **Wait for completion** by polling `GET /agents/{id}` until status returns to `idle`
4. **Collect results** from the API:
   - `GET /agents/{id}/conversations` — full message history with tool calls
   - `GET /agents/{id}/events` — execution trace with timings and models
   - `GET /agents/{id}/children` — spawned sub-agents
   - `GET /agents/{id}/messages` — inter-agent messages
   - `GET /agents/{id}/cost` — token usage and cost breakdown
   - `GET /memories` — extracted and stored memories
5. **Analyze and report** — compare observed behavior against expectations

## Prerequisites

- Backend must be running (`just dev-backend` or `just dev`)
- `curl` available (standard on Linux/macOS)
- Database state matters — some use cases expect a clean DB, others build on prior state

## Directory structure

```
docs/agent-drive/
├── README.md                              # This file
├── UC-001-greeting-memory.md              # Use case definition
├── UC-001-greeting-memory-2026-04-03.md   # Execution report
├── UC-002-*.md                            # Next use case
└── ...
```

## Conventions

### Use case files (`UC-{number}-{slug}.md`)

Define the test scenario:
- What to create (agents, templates, config)
- What prompts to send and in what order
- What to observe after each prompt
- What constitutes success vs failure
- Any preconditions (clean DB, specific config, prior use cases)

### Report files (`UC-{number}-{slug}-{YYYY-MM-DD}.md`)

Capture execution results:
- Timestamped — same use case can be run repeatedly to track changes
- Include raw data: events, conversations, memories, costs
- Analysis: what worked, what didn't, unexpected behavior
- Named to correlate with their use case definition

### Numbering

- `UC-001` through `UC-099` — basic capability tests (memory, tools, config)
- `UC-100` through `UC-199` — multi-agent scenarios (spawning, messaging, delegation)
- `UC-200` through `UC-299` — orchestration scenarios (decompose, parallel, pipeline)
- `UC-300+` — end-to-end showcase scenarios

## Running a use case

When asked to run a use case, Claude Code should:

1. Read the use case definition file
2. Check preconditions (backend running, DB state)
3. Execute each step via the API
4. Collect all observability data
5. Write the report file with timestamp
6. Summarize findings to the user
