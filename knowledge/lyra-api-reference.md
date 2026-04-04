# Lyra API Reference

## Base URL

http://localhost:8000

## Agent Management

### POST /agents
Create a new agent. Body: `{"name": "string", "config": {optional overrides}}`. Returns agent object with id, name, status, config.

### GET /agents/{id}
Get agent details including config, status, parent_agent_id.

### DELETE /agents/{id}
Delete an agent and its data.

### GET /agents/{id}/children
List child agents spawned by this agent.

### POST /agents/{id}/prompt
Send a prompt to the agent. Body: `{"message": "string"}`. Returns AgentResponse with content, conversation_id, events_emitted. Blocks until agent completes its turn.

### POST /agents/{id}/hitl-respond
Approve or deny a HITL gate. Body: `{"approved": true/false, "message": "optional"}`.

## Conversations & Events

### GET /agents/{id}/conversations
Full conversation history with all messages, tool calls, and results.

### GET /agents/{id}/events
All events for this agent with timestamps, types, modules, payloads, durations.

### GET /agents/{id}/events/stream
SSE stream of real-time events for this agent.

### GET /events/stream
SSE stream of all events across all agents.

## Messages

### GET /agents/{id}/messages
Inter-agent messages. Query params: direction (inbox/sent/all), message_type.

### POST /agents/{id}/messages
Send a message to an agent. Body: `{"content": "string", "message_type": "task|result|question|answer|guidance|status_update", "from_agent_id": "optional"}`.

## Tools

### GET /tools
List all registered tools with name, description, input_schema, tool_type, source.

### GET /tools/{name}/calls
History of calls to a specific tool.

## Skills

### GET /skills
List all loaded skills with name, description, parameters.

### GET /skills/{name}
Get a specific skill including its template.

## Templates

### GET /templates
List all agent templates.

### GET /templates/{name}
Get template details including config.

## Memory

### GET /memories
List all memories. Query params for search and filtering.

### GET /memories/{id}
Get a specific memory.

### DELETE /memories/{id}
Delete a memory.

### PATCH /memories/{id}
Update a memory (archive/unarchive, change importance).

## Cost

### GET /agents/{id}/cost
Token usage and cost breakdown by model for this agent.

### GET /cost
Platform-wide cost summary.

## Configuration

### GET /config/files
List all configuration files grouped by category.

### GET /config/file?path=...
Read a configuration file's content.

### PUT /config/file
Write/update a config file. Body: `{"path": "string", "content": "string"}`.

### DELETE /config/file?path=...
Delete a config file (agent configs, prompts, skills only).

### POST /config/reload
Reload skills, MCP servers, and templates without restart.

### POST /config/restart
Restart the backend server (triggers uvicorn reload).

### POST /config/mcp-servers/{name}/deploy
Human-only: approve deployment of an agent-managed MCP server.

## Health

### GET /health
Returns `{"status": "ok"}` when the service is running.
