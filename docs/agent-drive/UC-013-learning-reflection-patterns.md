# UC-013: Learning, Reflection & Capability Formalization

## Purpose

Validate the self-improvement loop: capability gap analysis, post-task reflection, tool analytics, pattern storage/retrieval, and the capability-acquirer template. Validates V3 Phase 4 deliverables.

## Preconditions

- Backend running at `http://localhost:8000` (restart after V3P4 merge)
- Existing skills, templates, and MCP servers in place
- Some prior agent activity in the DB (for tool_analytics to have data)

## Steps

### Step 1: Create agent and verify self-improvement tools

```
POST /agents
{"name": "learner"}
```

```
POST /agents/{id}/prompt
{"message": "What self-improvement and learning tools do you have?"}
```

**Expected:** Agent describes analyze_capabilities, reflect, tool_analytics, store_pattern, find_pattern.

### Step 2: Analyze capabilities for a task

```
POST /agents/{id}/prompt
{"message": "Use analyze_capabilities to check what we have available for this task: Write a technical blog post about the Lyra platform's memory system, including code examples from the actual codebase."}
```

**Expected:**
- Agent calls `analyze_capabilities`
- Returns available skills (summarize, code-review, etc.)
- Returns available templates (researcher, writer, editor, coder, critic)
- Returns relevant memories (if any exist from prior sessions)
- Returns an LLM-generated assessment identifying gaps and suggestions

**Verify in events:** LLM call for the assessment.

### Step 3: Find patterns for the task

```
POST /agents/{id}/prompt
{"message": "Use find_pattern to check if we have any orchestration patterns for blog post writing or content creation."}
```

**Expected:** Agent calls `find_pattern`. If no patterns exist yet, returns empty list. That's fine — we'll store one later.

### Step 4: Execute a small orchestrated task

```
POST /agents/{id}/prompt
{"message": "Orchestrate with parallel strategy: Research the three main components of the Lyra memory system (context memory, cross-context memory, long-term memory) and summarize each in 2-3 sentences."}
```

**Expected:** Orchestration runs with 3 parallel subtasks, produces synthesized output.

### Step 5: Reflect on the completed task

```
POST /agents/{id}/prompt
{"message": "Use the reflect tool to generate a retrospective on what we just did. Task was 'research and summarize the Lyra memory system components', outcome was the synthesized summary you just produced, tools used were orchestrate with parallel strategy."}
```

**Expected:**
- Agent calls `reflect` with task, outcome, tools_used
- LLM generates a retrospective (what worked, what was missing, improvements)
- Reflection stored as PROCEDURE memory
- Returns the reflection text

**Verify:**
```
GET /memories
```
Should include a new PROCEDURE memory with the reflection.

### Step 6: Store the orchestration pattern

```
POST /agents/{id}/prompt
{"message": "Store this as a reusable pattern using store_pattern: task_type is 'multi-component technical summary', strategy is 'parallel', subtasks are ['Research component A', 'Research component B', 'Research component C'], notes: 'Each component researched independently, works well for 3-5 independent topics'."}
```

**Expected:**
- Agent calls `store_pattern`
- Pattern stored as PROCEDURE memory
- Returns confirmation

### Step 7: Retrieve the stored pattern

```
POST /agents/{id}/prompt
{"message": "Use find_pattern to search for patterns related to 'summarizing multiple independent technical topics'."}
```

**Expected:**
- Agent calls `find_pattern`
- Returns the pattern stored in Step 6 (parallel strategy, 3 subtasks)
- Pattern content includes task_type and strategy

### Step 8: Tool analytics

```
POST /agents/{id}/prompt
{"message": "Use tool_analytics to show me which tools have been used the most, their success rates, and average durations."}
```

**Expected:**
- Agent calls `tool_analytics`
- Returns list of tools with call_count, success_rate, avg_duration_ms
- Should show orchestrate, recall, remember, and other tools used in this session

### Step 9: Tool analytics for specific tool

```
POST /agents/{id}/prompt
{"message": "Show me analytics specifically for the orchestrate tool."}
```

**Expected:** Filtered stats for orchestrate only.

### Step 10: Full recommended workflow

Test the complete workflow without explicit tool instructions:

```
POST /agents/{id}/prompt
{"message": "I need to produce a comparison of Python web frameworks: FastAPI, Django, and Flask. Before you start, analyze what capabilities we have, check for existing patterns, then execute the task, and after completion reflect on how it went and store the pattern if it worked well."}
```

**Expected:** Agent follows the recommended workflow:
1. `analyze_capabilities` or `find_pattern` first
2. Execute (orchestrate or direct)
3. `reflect` after completion
4. `store_pattern` if it worked well

**Check in events:** Whether the agent called the tools in the recommended order.

### Step 11: Spawn capability-acquirer

```
POST /agents/{id}/prompt
{"message": "I need the ability to generate PDF documents from markdown. Spawn a capability-acquirer sub-agent to find or build this capability."}
```

**Expected:**
- Agent calls `spawn_agent(template="capability-acquirer", task="Find or build a tool for generating PDF documents from markdown")`
- Sub-agent searches skills, templates, MCP servers
- Sub-agent reports back via send_message

**Check:**
```
GET /agents/{id}/children
```
Should show the capability-acquirer child agent.

### Step 12: Collect data

```
GET /agents/{id}/events
GET /agents/{id}/cost
GET /memories
```

## Success criteria

1. Agent knows all 5 self-improvement tools
2. analyze_capabilities returns structured report with available capabilities and gap assessment
3. find_pattern returns empty when no patterns exist, returns matches after storing
4. reflect generates retrospective and stores as PROCEDURE memory
5. store_pattern creates a retrievable PROCEDURE memory
6. tool_analytics returns usage statistics from event data
7. Tool analytics filters by specific tool name
8. Agent follows the recommended workflow (analyze → find → execute → reflect → store)
9. capability-acquirer template spawns and searches for capabilities

## What to report

- analyze_capabilities output: what was found, what gaps identified
- Reflection content: what insights were generated
- Pattern storage: content of stored pattern
- Tool analytics: top tools, success rates
- Whether the agent followed the recommended workflow autonomously
- Capability-acquirer sub-agent behavior
- Cost breakdown
- Any unexpected behavior
