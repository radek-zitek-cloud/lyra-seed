# V3 Phase 4 — Smoke Tests

## Test Environment
- Prerequisites: V3P2 complete, all prior smoke tests passing
- LLM calls: always mocked
- Embedding calls: mocked with deterministic fake vectors
- External APIs: never called

## Backend Smoke Tests

### ST-V3-4.1: analyze_capabilities returns structured report
- **Validates:** Capability gap analysis
- **Method:** Set up skills, templates, mock embeddings. Call analyze_capabilities with a task description.
- **Checks:**
  - Returns available skills, templates, MCP servers
  - Returns an LLM-generated assessment
  - Assessment references the task description

### ST-V3-4.2: analyze_capabilities works without embedding provider
- **Validates:** Graceful degradation
- **Checks:**
  - Returns results (all items, unsorted) without crashing

### ST-V3-4.3: capability-acquirer template exists
- **Validates:** Template files
- **Checks:**
  - `prompts/capability-acquirer.json` exists with expected config
  - `prompts/capability-acquirer.md` exists with workflow guidance
  - Config has no MCP tools (allowed_mcp_servers: [])

### ST-V3-4.4: reflect tool generates and stores retrospective
- **Validates:** Post-task reflection
- **Method:** Call reflect with task, outcome, and tools_used. Mock LLM.
- **Checks:**
  - LLM called with task context
  - Reflection stored as PROCEDURE memory
  - Memory content includes task and outcome references
  - Returns the reflection text

### ST-V3-4.5: reflect uses externalized prompt
- **Validates:** Prompt from prompts/system/reflect.md
- **Checks:**
  - File exists at prompts/system/reflect.md
  - Content references task, outcome, and tools

### ST-V3-4.6: tool_analytics aggregates from events
- **Validates:** Analytics from event data
- **Method:** Insert mock TOOL_CALL and TOOL_RESULT events, call tool_analytics
- **Checks:**
  - Returns call count, success rate, avg duration per tool
  - Specific tool query returns stats for that tool
  - No-arg query returns top tools by usage

### ST-V3-4.7: store_pattern stores a PROCEDURE memory
- **Validates:** Pattern storage
- **Method:** Call store_pattern with task_type, strategy, subtasks
- **Checks:**
  - Memory created with type PROCEDURE
  - Content includes task_type and strategy
  - Memory is searchable via recall

### ST-V3-4.8: find_pattern retrieves matching patterns
- **Validates:** Pattern retrieval via semantic search
- **Method:** Store a pattern, then search for it
- **Checks:**
  - Returns matching patterns ranked by relevance
  - Pattern content includes task_type and subtask descriptions

### ST-V3-4.9: App integration — tools registered
- **Validates:** Wiring in create_app
- **Method:** Create app, check tool list
- **Checks:**
  - analyze_capabilities appears in tools
  - reflect appears in tools
  - tool_analytics appears in tools
  - store_pattern and find_pattern appear in tools
