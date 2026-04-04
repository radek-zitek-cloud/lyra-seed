# UC-012: MCP Server Management

## Purpose

Validate the full MCP server lifecycle: adding pre-built servers, scaffolding custom servers, HITL-gated deployment, listing with semantic search, stopping, and hot-reload. Validates V3 Phase 2 deliverables.

## Preconditions

- Backend running at `http://localhost:8000` (restart after V3P2 merge)
- Firecrawl MCP server configured (for web search in Step 6)
- `mcp-servers/` directory exists and is empty

## Steps

### Step 1: Create agent and verify MCP management tools

```
POST /agents
{"name": "mcp-tester"}
```

```
POST /agents/{id}/prompt
{"message": "What MCP server management tools do you have?"}
```

**Expected:** Agent describes add_mcp_server, create_mcp_server, deploy_mcp_server, list_mcp_servers, stop_mcp_server.

### Step 2: List current MCP servers

```
POST /agents/{id}/prompt
{"message": "Use list_mcp_servers to show what MCP servers are available."}
```

**Expected:** Should show no agent-managed servers (empty mcp-servers/ directory). Platform-configured servers (filesystem, shell, firecrawl) are not shown here — those are in lyra.config.json.

### Step 3: Add a pre-built MCP server

```
POST /agents/{id}/prompt
{"message": "Add an MCP server called 'fetch' using command 'uvx' with args [\"mcp-fetch\"] and description 'Fetch web pages and convert to markdown'. Use add_mcp_server."}
```

**Expected:**
- Agent calls `add_mcp_server`
- Config file written to `mcp-servers/fetch.json`
- Returns success with config file path

**Verify on disk:**
```bash
cat mcp-servers/fetch.json
```

**Verify via API:**
```
GET /config/files
```
Should include fetch.json in mcp_servers section.

### Step 4: List servers after adding

```
POST /agents/{id}/prompt
{"message": "List MCP servers again to confirm the fetch server was added."}
```

**Expected:** `fetch` appears with deployed=true.

### Step 5: Semantic search over servers

```
POST /agents/{id}/prompt
{"message": "Search for MCP servers related to web content retrieval. Use list_mcp_servers with a query."}
```

**Expected:** `fetch` ranks first (description matches "web" + "content").

### Step 6: Scaffold a custom MCP server

```
POST /agents/{id}/prompt
{"message": "I need a custom MCP server that connects to a REST API at https://api.example.com. The server should provide tools: list_items, get_item, create_item. Use create_mcp_server with name 'example-api' and description 'CRUD operations for the Example API'."}
```

**Expected:**
- Agent calls `create_mcp_server`
- Directory created at `mcp-servers/example-api/`
- Config file at `mcp-servers/example-api.json` with deployed=false
- Returns the path for the agent to write code

**Verify on disk:**
```bash
ls mcp-servers/example-api/
cat mcp-servers/example-api.json
```

### Step 7: Deploy requires HITL

```
POST /agents/{id}/prompt
{"message": "Deploy the example-api server using deploy_mcp_server."}
```

**Expected:**
- Agent calls `deploy_mcp_server`
- Returns HITL request with server details (name, description, command, workdir)
- Config still shows deployed=false

**Verify:**
```bash
cat mcp-servers/example-api.json | python3 -c "import sys,json; print(json.load(sys.stdin)['deployed'])"
```
Should print `false`.

### Step 8: Simulate HITL approval

```
POST /agents/{id}/prompt
{"message": "The deployment was approved by the human. Call deploy_mcp_server again for example-api with approved=true."}
```

**Expected:**
- Config updated to deployed=true
- Returns success with deployment confirmation

**Verify:**
```bash
cat mcp-servers/example-api.json | python3 -c "import sys,json; print(json.load(sys.stdin)['deployed'])"
```
Should print `true`.

### Step 9: Stop a server

```
POST /agents/{id}/prompt
{"message": "Stop the fetch MCP server using stop_mcp_server."}
```

**Expected:**
- Returns success
- Config updated to deployed=false

### Step 10: Cannot stop platform servers

```
POST /agents/{id}/prompt
{"message": "Try to stop the filesystem MCP server."}
```

**Expected:** Agent should report it cannot stop platform-configured servers. If it tries `stop_mcp_server(name="filesystem")`, it gets an error.

### Step 11: Name validation

```
POST /agents/{id}/prompt
{"message": "Try to add an MCP server with name 'my server!' and command 'echo'."}
```

**Expected:** Rejected — invalid name.

### Step 12: Hot-reload via config editor

Add a config file manually, then reload:

```bash
echo '{"name":"manual-test","description":"Manually added","command":"echo","args":["test"],"managed":true,"deployed":true}' > mcp-servers/manual-test.json
```

```
POST /config/reload
```

Then ask the agent:
```
POST /agents/{id}/prompt
{"message": "List MCP servers again — a new one should have appeared after reload."}
```

**Expected:** `manual-test` appears in the list.

### Step 13: Autonomous MCP server discovery

Test whether the agent can find and add an MCP server on its own:

```
POST /agents/{id}/prompt
{"message": "I need the ability to interact with GitHub repositories — search for issues, read PRs, etc. Can you find an existing MCP server for that and add it?"}
```

**Expected:** Agent should:
1. Search the web (via firecrawl or shell+curl) for GitHub MCP servers
2. Find something like `@modelcontextprotocol/server-github` or similar
3. Call `add_mcp_server` to add it

This tests the full self-evolution loop: identify need → search → add capability.

### Step 14: Collect data

```
GET /agents/{id}/events
GET /agents/{id}/cost
GET /config/files
```

## Success criteria

1. Agent knows all 5 MCP management tools
2. add_mcp_server writes config file and marks deployed
3. create_mcp_server scaffolds directory with deployed=false
4. deploy_mcp_server returns HITL request before deploying
5. deploy_mcp_server with approved=true marks deployed
6. list_mcp_servers returns all managed servers
7. Semantic search ranks relevant servers first
8. stop_mcp_server stops managed servers
9. Platform servers cannot be stopped
10. Name validation rejects invalid names
11. Hot-reload detects new config files
12. Agent can autonomously discover and add MCP servers from the web

## What to report

- Config files created on disk
- HITL request content (what the human would see)
- Deployed status before and after approval
- Semantic search results
- Whether the agent searched the web autonomously in Step 13
- Hot-reload detection result
- Cost breakdown
- Any errors or unexpected behavior
