# Lyra Agent Templates

## What Are Templates

Templates are pre-defined agent roles with specialized system prompts and configurations. When spawning a sub-agent, use `template` to apply a role. Templates are pairs of files in the `prompts/` directory: `{name}.json` (config) and `{name}.md` (system prompt).

## Available Templates

### default

The base template applied to all agents. Documents the full platform capability set: memory, sub-agents, messaging, orchestration, skills, discovery, MCP management, and self-improvement.

- HITL: never
- MCP: all servers
- Temperature: 0.7

### coder

Autonomous Python build agent. Follows a 7-phase workflow: requirements analysis, implementation plan, environment setup, TDD test writing, code implementation, test execution, and final validation. Produces tested Python projects.

- Model: gpt-5.4 (needs stronger model for complex code)
- Temperature: 0.3
- Max iterations: 40
- MCP: filesystem + shell only
- Auto-extract: false
- Use case: spawn_agent(template="coder", task="Build a Python CLI that...")

### researcher

Deep research agent producing structured output with executive summary, detailed findings, key takeaways, and caveats. Prioritizes depth over breadth.

- Temperature: 0.5
- MCP: none (pure reasoning)
- Auto-extract: false
- Use case: spawn_agent(template="researcher", task="Research the current state of...")

### writer

Text production agent. Takes research or instructions as input, produces polished prose. Higher temperature for stylistic variation.

- Temperature: 0.7
- MCP: none (pure reasoning)
- Auto-extract: false
- Use case: spawn_agent(template="writer", task="Write a blog post based on this research: ...")

### editor

Reviews and improves text to conform to a stated purpose, audience, and quality standard. Returns edited text with a summary of changes.

- Temperature: 0.3 (precision over creativity)
- MCP: none
- Use case: spawn_agent(template="editor", task="Edit this text for a technical audience: ...")

### critic

Structured critique of any work product. Returns verdict (yes/partially/no), strengths, issues ranked by severity, and top 3 recommendations.

- Temperature: 0.4
- MCP: none
- Use case: spawn_agent(template="critic", task="Review this blog post for accuracy: ...")

### hitl-worker

Generic worker with human-in-the-loop approval on every tool call. For sensitive operations.

- Temperature: 0.3
- HITL: always_ask
- MCP: all servers
- Use case: spawn_agent(template="hitl-worker", task="Update the production config...")

### non-hitl-worker

Generic worker running fully autonomous. All tool calls execute without approval.

- Temperature: 0.3
- HITL: never
- MCP: all servers

### capability-acquirer

Specialized sub-agent for finding or building missing capabilities. Follows search-first workflow: check skills → templates → MCP servers → web search → build if nothing found.

- Temperature: 0.3
- MCP: none (uses platform tools)
- Use case: spawn_agent(template="capability-acquirer", task="Find or build a tool for PDF generation")

## Composition Patterns

### Research-to-document pipeline

1. Spawn researcher to investigate a topic
2. Spawn writer with the research as input
3. Spawn editor to polish the draft
4. Optionally spawn critic for quality review

### Code with review

1. Spawn coder to build a project
2. Spawn critic to review the output

### Supervised vs unsupervised

- hitl-worker for operations needing human approval per action
- non-hitl-worker for safe unattended tasks

### Capability acquisition

1. Agent identifies a gap via analyze_capabilities
2. Spawns capability-acquirer to find or build the missing capability
3. Acquirer reports back with what was found/built

## Creating New Templates

1. Create `prompts/{name}.json` with config overrides
2. Create `prompts/{name}.md` with the system prompt
3. Use via: spawn_agent(template="{name}", task="...")

Fields not set fall back to default.json → lyra.config.json → hardcoded defaults.

## Discovering Templates

Agents can find templates via:
- `list_templates()` — list all available templates
- `list_templates(query="code generation")` — semantic search
- `get_template(name="coder")` — get specific template details
- `discover(query="...")` — unified search including templates
