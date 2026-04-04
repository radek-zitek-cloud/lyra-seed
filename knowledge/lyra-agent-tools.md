# Lyra Agent Tools Reference

## Tool Categories

Every agent has access to tools based on its configuration. Tools are grouped by provider.

## Memory Tools

| Tool | Purpose |
|------|---------|
| remember | Store a memory with type, importance, and visibility |
| recall | Semantic search over memories |
| forget | Delete a specific memory by ID |

Memory types: fact, preference, decision, outcome, procedure, tool_knowledge, domain_knowledge. Visibility: public (all agents), private (agent only), team (parent+children).

Automatic extraction runs after each response — no need to explicitly remember routine facts.

## Sub-Agent Tools

| Tool | Purpose |
|------|---------|
| spawn_agent | Create and start a sub-agent (async, returns immediately) |
| wait_for_agent | Block until child completes, return result |
| check_agent_status | Non-blocking status check |
| get_agent_result | Get child's last response |
| list_child_agents | List all spawned children |
| stop_agent | Cancel a running child |
| dismiss_agent | Mark child as permanently completed |
| send_message | Send typed message to another agent |
| receive_messages | Check inbox for messages |

Message types: task, result, question, answer, guidance, status_update. Idle agents auto-wake on task/guidance messages.

## Orchestration Tools

| Tool | Purpose |
|------|---------|
| decompose_task | Break a task into a structured plan without executing |
| orchestrate | End-to-end: decompose + execute + synthesize |

Strategies: sequential (ordered), parallel (concurrent), pipeline (chained output-to-input).
Failure policies per subtask: retry, skip, escalate, reassign.

Important: orchestrated subtasks are standalone LLM calls without tool access. For subtasks needing tools, use spawn_agent instead.

## Skill Tools

| Tool | Purpose |
|------|---------|
| list_skills | List available skills with optional semantic search |
| create_skill | Create a new skill .md file |
| test_skill | Dry-run a template with LLM evaluation (PASS/FAIL) |
| update_skill | Update existing skill (versions old file) |

Skills are .md files with YAML frontmatter (name, description, parameters) and a template body with {{parameter}} placeholders.

## Discovery Tools

| Tool | Purpose |
|------|---------|
| discover | Search across ALL sources: skills, templates, MCP servers, knowledge, memories |
| list_templates | List agent templates with semantic search |
| get_template | Get template details including config |

discover() is the unified entry point — use it before deciding how to approach a task.

## Knowledge Tools

| Tool | Purpose |
|------|---------|
| search_knowledge | Semantic search over knowledge base documents |
| ingest_document | Add a .md file to the knowledge base at runtime |

Knowledge base documents are chunked by headings, embedded, and stored in ChromaDB. Results include source file and heading path.

## Capability Tools

| Tool | Purpose |
|------|---------|
| analyze_capabilities | Search all sources + LLM gap assessment |
| reflect | Post-task retrospective stored as PROCEDURE memory |
| tool_analytics | Query tool usage statistics from event data |
| store_pattern | Save orchestration pattern for reuse |
| find_pattern | Find patterns matching a task description |

## MCP Server Management

| Tool | Purpose |
|------|---------|
| list_mcp_servers | List agent-managed MCP servers with search |
| add_mcp_server | Add a pre-built MCP server package |
| create_mcp_server | Scaffold custom server directory |
| deploy_mcp_server | Request deployment (requires human approval) |
| stop_mcp_server | Stop an agent-managed server |

## MCP Tools (from connected servers)

Depends on configured MCP servers. Common examples:
- **filesystem**: fast_read_file, fast_write_file, fast_list_directory, fast_search_files, etc.
- **shell**: shell_execute (limited to allowed commands)
- **firecrawl**: firecrawl_search, firecrawl_scrape
- **microblog-api**: list_posts, create_post, edit_post, delete_post, list_tags, get_profile
