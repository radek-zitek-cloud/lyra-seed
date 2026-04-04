# Lyra UI Guide

## Pages

The web frontend at http://localhost:3000 has 5 main pages.

## Home Page (/)

The agent list. Shows all agents with their status, cost, and a create form.

### Creating Agents

Type a name and click CREATE. If a matching template exists in prompts/{name}.json + {name}.md, it loads automatically. Otherwise the default template is used.

### Agent Cards

Each card shows: agent name, status badge (idle/running/waiting_hitl/completed/failed), accumulated cost, and a DELETE button.

### Status Indicators

- **idle** — agent waiting for a prompt
- **running** — agent processing (LLM call or tool execution)
- **waiting_hitl** — agent paused at a HITL approval gate
- **completed** — permanently done (dismissed)
- **failed** — encountered an unrecoverable error

## Agent Detail Page (/agents/{id})

Two-column layout showing the agent's conversation and events.

### Left Column

- **Conversation panel** — chat-style view of human and assistant messages. Tool calls and results are shown inline.
- **Prompt input** — text field to send messages. Disabled while agent is running.
- **HITL panel** — appears when agent is waiting for approval. Shows what the agent wants to do, approve/deny buttons.
- **Sub-agents bar** — shows child agents with status badges and links to their detail pages.
- **Parent link** — if this is a child agent, link to parent.
- **Message panel** — inter-agent messages with type badges, direction indicators, and send input.

### Right Column

- **Event timeline** — chronological list of all events, color-coded by type. Each event expandable to show full payload including tool arguments, LLM model, duration, etc.
- **Connection status** — LIVE/OFFLINE indicator for SSE stream.

## Memory Browser (/memories)

Browse all stored memories across all agents. Features:
- Semantic search
- Filter by memory type and status
- Archive/unarchive/delete operations
- Shows visibility, importance, agent name, timestamps

## Graph View (/graph)

Interactive visualization of the agent network using React Flow.
- Agent nodes showing name, model, status
- Parent-child edges
- Orchestration subtask nodes inside agent containers
- Message flow edges between agents
- Dashboard with aggregate metrics
- Spawn agent form

## Config Editor (/config)

File editor for all configuration. Sidebar lists files grouped by category:
- Platform Config (lyra.config.json, .env)
- Agent Configs (prompts/*.json)
- Agent Prompts (prompts/*.md)
- System Prompts (prompts/system/*.md)
- Skills (skills/*.md)
- MCP Servers (mcp-servers/*.json)

Features:
- Monospace text editor
- Save/Cancel buttons
- Delete with inline confirmation (protected for platform config and system prompts)
- Cursor-aware context help bar (shows description of the config key at cursor)
- RELOAD CONFIG button (reloads skills and MCP server configs)
- RESTART SERVER button with confirmation (for changes requiring restart)

## Real-Time Updates

The UI uses Server-Sent Events (SSE) for real-time updates:
- Event timeline updates live as events stream in
- Agent status changes reflected immediately
- HITL requests trigger notifications
- Connection status indicator shows LIVE/OFFLINE
