# Lyra Self-Improvement System

## Overview

Lyra agents can analyze their own capabilities, learn from experience, and improve over time. This is the foundation of the platform's self-evolution capability.

## The Self-Improvement Loop

### Before a Task

1. **discover(query)** — search across all sources to understand what's available
2. **find_pattern(task)** — check if a similar task was solved before
3. **analyze_capabilities(task)** — get a structured gap analysis with suggestions

### During a Task

- Use existing skills, templates, and tools
- If a capability is missing: search the web for MCP packages, create skills, or scaffold custom servers
- Spawn specialized sub-agents for different parts of the work

### After a Task

1. **reflect(task, outcome, tools_used)** — generate a retrospective on what worked and what didn't
2. **store_pattern(task_type, strategy, subtasks)** — save the approach for future reuse

## Capability Discovery

### discover(query)

The unified search tool. Searches across all 5 sources in one call:
- Skills (reusable prompt templates)
- Templates (agent roles)
- MCP servers (tool servers)
- Knowledge base (documented information)
- Memories (past experiences)

Returns ranked results with type, name, description, and relevance score.

### analyze_capabilities(task)

Uses discover internally, then adds an LLM assessment of gaps. Returns:
- All discovered capabilities relevant to the task
- An LLM-generated analysis of what's available vs what's missing
- Suggestions for how to fill gaps

## Learning from Experience

### reflect(task, outcome, tools_used)

Generates a post-task retrospective via LLM. Stored as a PROCEDURE memory with [REFLECTION] prefix. The reflection covers:
- What approach was taken
- Which tools were most effective
- What was missing or could improve
- What to remember for similar tasks

Reflections are searchable via recall and find_pattern.

### store_pattern(task_type, strategy, subtasks)

Saves a successful orchestration approach as a PROCEDURE memory with [PATTERN] prefix. Next time a similar task comes up, find_pattern retrieves it so the agent doesn't decompose from scratch.

### tool_analytics(tool_name?)

Queries tool usage statistics from event data:
- Call count
- Success rate
- Average duration

Helps the agent choose the right tool — "which tool works best for web scraping?"

## Capability Acquisition

When analyze_capabilities identifies a gap:

### For prompt-based capabilities
1. `test_skill` — dry-run a template
2. `create_skill` — create a new skill if test passes

### For existing MCP packages
1. Search the web (firecrawl) for MCP server packages
2. `add_mcp_server` — add the package

### For custom integrations
1. `create_mcp_server` — scaffold the server directory
2. Write the server code (directly or via coder sub-agent)
3. `deploy_mcp_server` — request deployment (human approval required)

### Using the capability-acquirer template
Spawn a specialized sub-agent: `spawn_agent(template="capability-acquirer", task="Find or build a tool for X")`. It follows the search-first workflow automatically.

## Example: Full Self-Improvement Cycle

1. User asks: "Produce a competitive analysis of cloud providers"
2. Agent calls `analyze_capabilities` → finds researcher template, summarize skill, no specific cloud knowledge
3. Agent calls `find_pattern("competitive analysis")` → finds a stored parallel pattern
4. Agent orchestrates with parallel strategy, one subtask per provider
5. After completion: `reflect` → "parallel worked well, but subtasks were generic — next time use search_knowledge for grounding"
6. `store_pattern("cloud competitive analysis", "parallel", [...])` → saved for future use
7. Next time a similar task comes: `find_pattern` retrieves the approach + the reflection's lessons
