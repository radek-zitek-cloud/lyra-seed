# UC-008: Per-Agent Tool Scoping

## Purpose

Validate that agents can be configured with restricted tool access via `allowed_mcp_servers` and `allowed_tools`. Verify that scoping affects what the LLM sees, that children inherit parent scope, and that templates can override. Validates V2 Phase 4 deliverables.

## Preconditions

- Backend running at `http://localhost:8000`
- MCP servers configured: `filesystem` and `shell`
- Agent templates available: `researcher` (no MCP), `coder` (filesystem + shell)

## Steps

### Step 1: Verify baseline — unscoped agent sees all tools

```
POST /agents
{"name": "full-access"}
```

```
POST /agents/{id}/prompt
{"message": "List all the tools you have available. Just list the tool names, grouped by category."}
```

**Expected:** Agent lists all tools including filesystem tools (fast_read_file, etc.), shell (shell_execute), memory tools, spawner tools, and orchestration tools.

### Step 2: Create MCP-scoped agent (filesystem only)

```
POST /agents
{"name": "fs-only", "config": {"allowed_mcp_servers": ["filesystem"]}}
```

```
POST /agents/{id}/prompt
{"message": "List all the tools you have available. Just list the tool names, grouped by category."}
```

**Expected:**
- Filesystem tools present (fast_read_file, fast_write_file, etc.)
- Shell tool (shell_execute) NOT present
- Core tools present (remember, recall, spawn_agent, orchestrate, etc.)

### Step 3: Verify scoped agent cannot see restricted tools

```
POST /agents/{id}/prompt
{"message": "Run the command 'echo hello' using the shell."}
```

**Expected:** Agent should say it doesn't have shell access or doesn't have a tool for running commands. It should NOT attempt to call shell_execute.

### Step 4: Verify scoped agent can use allowed tools

```
POST /agents/{id}/prompt
{"message": "List the files in /home/radek/Code/lyra-seed/prompts/ directory."}
```

**Expected:** Agent calls a filesystem tool (fast_list_directory) and returns the directory listing. Filesystem tools work normally.

### Step 5: Create agent with no MCP tools

```
POST /agents
{"name": "no-tools", "config": {"allowed_mcp_servers": []}}
```

```
POST /agents/{id}/prompt
{"message": "List all the tools you have available."}
```

**Expected:** Only core tools listed — memory (remember, recall, forget), spawner (spawn_agent, etc.), orchestration (decompose_task, orchestrate). No filesystem or shell tools.

### Step 6: Test allowed_tools whitelist

```
POST /agents
{"name": "memory-only", "config": {"allowed_tools": ["remember", "recall", "forget"]}}
```

```
POST /agents/{id}/prompt
{"message": "List all the tools you have available."}
```

**Expected:** Only remember, recall, and forget. No filesystem, shell, spawner, or orchestration tools.

### Step 7: Test template-based scoping (researcher)

```
POST /agents
{"name": "researcher"}
```

**Expected config:** `allowed_mcp_servers: []` (from researcher.json).

```
POST /agents/{id}/prompt
{"message": "Do you have access to filesystem or shell tools?"}
```

**Expected:** Agent confirms it does not have filesystem or shell tools. Only memory and other core tools.

### Step 8: Test template-based scoping (coder)

```
POST /agents
{"name": "coder"}
```

**Expected config:** `allowed_mcp_servers: ["filesystem", "shell"]` (from coder.json).

Verify via API:
```
GET /agents/{id}
```

**Expected:** Config shows `allowed_mcp_servers: ["filesystem", "shell"]`.

### Step 9: Child inherits parent's scope

Create a parent with restricted scope, spawn a child without a template:

```
POST /agents
{"name": "restricted-parent", "config": {"allowed_mcp_servers": ["filesystem"]}}
```

```
POST /agents/{id}/prompt
{"message": "Spawn a sub-agent named 'child-worker' with task 'List your available tools and report back via send_message'."}
```

Wait for child to complete, then check child's config:

```
GET /agents/{parent_id}/children
GET /agents/{child_id}
```

**Expected:** Child's `allowed_mcp_servers` is `["filesystem"]` (inherited from parent).

### Step 10: Child template overrides parent's scope

Same restricted parent, spawn with coder template:

```
POST /agents/{id}/prompt
{"message": "Spawn a sub-agent named 'coder-child' with template 'coder' and task 'List your available tools and report back via send_message'."}
```

Check child's config:

```
GET /agents/{child_id}
```

**Expected:** Child's `allowed_mcp_servers` is `["filesystem", "shell"]` (from coder template, overriding parent's `["filesystem"]`).

### Step 11: Compare tool schema sizes

For each agent created, check the events to see how many tools were in the schema passed to the LLM:

```
GET /agents/{id}/events
```

Look at `llm_request` events — the tool count should differ:
- Full access: ~40 tools
- Filesystem only: ~39 tools (40 minus shell_execute)
- No MCP: ~14 tools
- Memory only: 3 tools

This validates the token savings motivation for per-agent scoping.

## Success criteria

1. Unscoped agent sees all 40 tools
2. `allowed_mcp_servers: ["filesystem"]` hides shell but keeps filesystem + core tools
3. `allowed_mcp_servers: []` hides all MCP tools, keeps core tools
4. `allowed_tools` whitelist restricts to exactly those tools
5. Scoped agent cannot call restricted tools (doesn't even try)
6. Scoped agent can use allowed tools normally
7. Template-based scoping works (researcher gets no MCP, coder gets fs+shell)
8. Child inherits parent's scope when no template specified
9. Child template overrides parent's scope
10. Tool schema size varies by scope (token savings)

## What to report

- Tool lists from each scoped agent (what they see vs what's hidden)
- Whether the agent attempted to use restricted tools
- Config verification for template-based and inherited agents
- Tool schema sizes per agent type
- Any unexpected behavior (tools leaking through scope, tools missing that should be present)
- Cost comparison between full-access and scoped agents (fewer tools = fewer tokens)
