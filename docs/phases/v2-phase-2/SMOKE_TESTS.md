# V2 Phase 2 — Smoke Tests

## Test Environment
- Prerequisites: V2P1 complete, all prior smoke tests passing
- LLM calls: always mocked
- External APIs: never called

## Backend Smoke Tests

### ST-V2-2.1: AgentMessage model and MessageType enum
- **Validates:** Data models exist with correct fields
- **Checks:**
  - MessageType has: TASK, RESULT, QUESTION, ANSWER, GUIDANCE, STATUS_UPDATE
  - AgentMessage has: id, from_agent_id, to_agent_id, content, message_type, timestamp, in_reply_to

### ST-V2-2.2: SqliteMessageRepo CRUD
- **Validates:** Message persistence
- **Checks:**
  - Create message, get by ID
  - List messages for agent (inbox)
  - List messages between two agents
  - Delete message

### ST-V2-2.3: spawn_agent returns immediately
- **Validates:** Async spawn behavior
- **Checks:**
  - spawn_agent tool call returns within 1 second
  - Returns child_agent_id and status "running"
  - Child agent exists in repo with RUNNING status

### ST-V2-2.4: Child runs to completion in background
- **Validates:** Background task execution
- **Checks:**
  - After spawn returns, child eventually reaches IDLE
  - Child has conversation with assistant response
  - AGENT_COMPLETE event emitted

### ST-V2-2.5: wait_for_agent blocks until complete
- **Validates:** Async wait mechanism
- **Checks:**
  - Calling wait_for_agent on running child blocks
  - Returns when child completes
  - Returns child content

### ST-V2-2.6: check_agent_status non-blocking
- **Validates:** Status check tool
- **Checks:**
  - Returns immediately with current status
  - Includes agent name and last message preview

### ST-V2-2.7: stop_agent cancels running child
- **Validates:** Graceful stop
- **Checks:**
  - Running child can be stopped
  - Child status set to IDLE after stop
  - Background task cancelled

### ST-V2-2.8: send_message creates message and emits events
- **Validates:** Message sending
- **Checks:**
  - Message persisted in repo
  - MESSAGE_SENT event emitted on sender
  - MESSAGE_RECEIVED event emitted on target

### ST-V2-2.9: receive_messages returns inbox
- **Validates:** Message receiving
- **Checks:**
  - Returns messages addressed to agent
  - Supports message_type filter
  - Returns empty list when no messages

### ST-V2-2.10: dismiss_agent sets COMPLETED
- **Validates:** Agent dismissal
- **Checks:**
  - Child status set to COMPLETED
  - Cannot send further tasks to dismissed agent

### ST-V2-2.11: Runtime GUIDANCE injection
- **Validates:** Mid-execution message handling
- **Checks:**
  - GUIDANCE message injected into conversation context
  - Agent sees the guidance in its next LLM call

### ST-V2-2.12: Message API GET endpoint
- **Validates:** GET /agents/{id}/messages
- **Checks:**
  - Returns messages for agent
  - Supports direction filter (inbox/sent/all)

### ST-V2-2.13: Message API POST endpoint
- **Validates:** POST /agents/{id}/messages
- **Checks:**
  - Creates message from human to agent
  - Returns created message

### ST-V2-2.14: Reusable lifecycle
- **Validates:** Sending new task to idle child
- **Checks:**
  - Send TASK message to idle child
  - Child can process new prompt via POST /agents/{id}/prompt
  - Conversation history preserved from previous task

## Frontend Smoke Tests

### ST-V2-2.15: MessagePanel renders messages
- **Validates:** Message list component
- **Checks:**
  - Messages displayed with type badges
  - Direction indicators (sent/received)
  - Timestamps shown

### ST-V2-2.16: MessagePanel send input
- **Validates:** Message send UI
- **Checks:**
  - Input field and send button present
  - Message type selector present
