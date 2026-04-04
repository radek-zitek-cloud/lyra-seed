# UC-012: MCP Server Management — Report 2026-04-04

## Execution context

- **Date:** 2026-04-04 ~15:35 UTC
- **Agent ID:** `220d2091-c260-4f57-9bcb-6028bf87db3b`
- **Agent name:** `mcp-tester`
- **Model:** openai/gpt-5.4

## Results by step

### Step 1: Tool awareness — PASS
Agent listed all 5 MCP management tools correctly.

### Step 2: Empty listing — PASS
No agent-managed servers initially.

### Step 3: Add pre-built server — PASS
Added `fetch` server (uvx mcp-fetch). Config written with managed=true, deployed=true.

### Step 4: List after add — PASS
`fetch` appears with correct status.

### Step 5: Semantic search — PASS
Search for "web content retrieval" returned `fetch` as match.

### Step 6: Scaffold custom server — PASS
Created `mcp-servers/example-api/` directory and config with deployed=false.

### Step 7-8: Deploy HITL — FAIL (design issue)
The agent called `deploy_mcp_server(name="example-api", approved="true")` directly — it set the `approved` parameter itself, bypassing the HITL gate entirely. The LLM read the tool schema, saw the `approved` parameter, and set it to `"true"` on the first call.

**Root cause:** The HITL gate is implemented as a tool argument that the LLM can control. This is not a real HITL gate — it's a suggestion that the LLM ignored. A proper HITL gate should be enforced by the runtime (like the existing `hitl_policy` mechanism), not by the tool's own parameter.

### Step 9: Stop server — PASS
`fetch` stopped, config updated to deployed=false.

### Step 10: Cannot stop platform servers — PASS
`filesystem` rejected: "not found in agent-managed servers."

### Step 11: Name validation — PASS
"my server!" rejected with clear error message.

### Step 12: Hot-reload — PASS
Manually added `manual-test.json`, called `/config/reload`, agent confirmed 3 configs (2 deployed).

### Step 13: Autonomous discovery — PASS
Agent autonomously:
1. `firecrawl_search` — searched for GitHub MCP servers
2. `firecrawl_scrape` — scraped a result
3. Two more `firecrawl_search` — refined
4. `add_mcp_server` — added `@modelcontextprotocol/server-github`

This is the full self-evolution loop in action: identify need → search web → add capability.

## Final server inventory

| Server | Deployed | How added |
|--------|----------|-----------|
| example-api | true | Scaffolded + deployed (HITL bypassed) |
| fetch | false | Added pre-built, then stopped |
| github | true | Autonomously discovered and added |
| manual-test | true | Manually added + reloaded |

## Cost

| Model | Calls | Cost |
|-------|-------|------|
| gpt-5.4 | 27 | $1.0527 |
| gpt-5.4-mini | 17 | $0.0227 |
| text-embedding-3-large | 43 | $0.0002 |
| **Total** | **87** | **$1.0756** |

## Summary

| Criterion | Result |
|-----------|--------|
| Tool awareness | PASS |
| add_mcp_server writes config | PASS |
| create_mcp_server scaffolds directory | PASS |
| deploy_mcp_server HITL gate | FAIL (bypassed by LLM) |
| list_mcp_servers with search | PASS |
| stop_mcp_server | PASS |
| Platform servers protected | PASS |
| Name validation | PASS |
| Hot-reload detects new configs | PASS |
| Autonomous web discovery | PASS |

**Overall: PASS with one critical design issue.**

## Issues found

### Critical: deploy_mcp_server HITL gate is bypassable

The `approved` parameter in the tool schema lets the LLM set it to `"true"` directly, completely bypassing the human approval gate. This defeats the purpose of HITL for deploying agent-created code.

**Fix options:**
1. Remove `approved` from the tool schema — make deployment always go through the runtime's HITL mechanism (`hitl_policy: "always_ask"` forced for this tool)
2. Use a separate confirmation flow — first call returns a deployment ID, human approves via API/UI, second call references the approval ID
3. Remove `approved` and have the tool always return `requires_hitl: true` — the runtime handles the gate

Option 1 is simplest and uses existing infrastructure. The runtime already has HITL gates that the LLM cannot bypass.
