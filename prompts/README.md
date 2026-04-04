# Agent Templates

This directory contains agent configuration and system prompt templates. Each agent template consists of two files:

- `{name}.json` — configuration overrides (model, temperature, HITL policy, tool access, etc.)
- `{name}.md` — system prompt defining the agent's personality, capabilities, and behavior

When an agent is created with a name or template, the platform looks for matching files here. See `docs/CONFIGURATION_GUIDE.md` for the full resolution chain.

---

## Templates

### default

The base template applied to all agents unless overridden. Documents the full platform capability set: memory system, sub-agent spawning, inter-agent messaging, and task orchestration.

- **Use case:** General-purpose assistant, direct interaction with the human
- **HITL:** never
- **MCP servers:** all (no restriction)

### coder

Autonomous Python build agent. Receives a requirements definition and executes a 7-phase workflow: requirements analysis, implementation plan, environment setup, TDD, code implementation, test execution, and final validation. Produces tested, production-quality Python projects under `work/coder/`.

- **Use case:** `spawn_agent` with `template: "coder"` for code generation tasks
- **Model:** gpt-5.4 (needs the stronger model for complex code)
- **Temperature:** 0.3
- **Max iterations:** 40 (long-running builds)
- **HITL:** never
- **MCP servers:** filesystem, shell

### researcher

Deep research agent. Produces structured research with executive summary, detailed findings, key takeaways, and caveats. Focuses on depth over breadth.

- **Use case:** `spawn_agent` with `template: "researcher"` for investigation tasks
- **Temperature:** 0.5
- **HITL:** never
- **MCP servers:** none (pure reasoning)

### writer

Text production agent. Takes research material or instructions and produces polished, well-structured prose. Higher temperature for stylistic variation.

- **Use case:** `spawn_agent` with `template: "writer"` after a researcher provides findings
- **Temperature:** 0.7
- **HITL:** never
- **MCP servers:** none (pure reasoning)

### editor

Text editing agent. Reviews and improves existing text to conform to a stated purpose, audience, and quality standard. Returns the edited text in full plus a summary of changes made.

- **Use case:** `spawn_agent` with `template: "editor"` to polish writer output
- **Temperature:** 0.3 (precision over creativity)
- **HITL:** never
- **MCP servers:** none (pure reasoning)

### critic

Structured critique agent. Reviews any work product (code, writing, plans, analyses) and provides a verdict, strengths, issues ranked by severity, and top 3 recommendations. Useful for self-review — a parent agent can spawn a critic to evaluate its own output.

- **Use case:** `spawn_agent` with `template: "critic"` for quality review
- **Temperature:** 0.4
- **HITL:** never
- **MCP servers:** none (pure reasoning)

### hitl-worker

Generic worker with human-in-the-loop approval. Every tool call requires human approval before execution. Use when the task involves sensitive operations.

- **Use case:** `spawn_agent` with `template: "hitl-worker"` for supervised tasks
- **Temperature:** 0.3
- **HITL:** always_ask
- **MCP servers:** all

### non-hitl-worker

Generic worker running fully autonomous. Same as hitl-worker but all tool calls execute without approval.

- **Use case:** `spawn_agent` with `template: "non-hitl-worker"` for unsupervised tasks
- **Temperature:** 0.3
- **HITL:** never
- **MCP servers:** all

### capability-acquirer

Specialized sub-agent for finding or building missing capabilities. Follows a search-first workflow: check existing skills → templates → MCP servers → web search → build if nothing found.

- **Use case:** `spawn_agent` with `template: "capability-acquirer"` when the parent identifies a capability gap
- **Temperature:** 0.3
- **HITL:** never
- **MCP servers:** none (uses platform tools: list_skills, list_templates, list_mcp_servers, create_skill, add_mcp_server)

---

## Composition patterns

These templates are designed to be composed in multi-agent workflows:

**Research-to-document pipeline:**
1. Spawn `researcher` to investigate a topic
2. Spawn `writer` with the research output as the task
3. Spawn `editor` to polish the draft
4. Optionally spawn `critic` to review the final version

**Code with review:**
1. Spawn `coder` to build a project
2. Spawn `critic` to review the output

**Supervised vs unsupervised delegation:**
- Use `hitl-worker` when you want the human to approve each tool call
- Use `non-hitl-worker` when the task is safe to run unattended

---

## Internal system prompts

The `system/` subdirectory contains prompts used by the platform internally (not agent-facing):

| File | Used by | Purpose |
|------|---------|---------|
| `system/decompose_task.md` | TaskDecomposer | Task decomposition instructions |
| `system/synthesize_results.md` | ResultSynthesizer | Result synthesis instructions |
| `system/extract_facts.md` | FactExtractor | Automatic fact extraction from conversations |
| `system/summarize.md` | ContextManager | Context compression summarization |

---

## Creating a new template

1. Create `{name}.json` with configuration overrides (see `docs/CONFIGURATION_GUIDE.md` for all fields)
2. Create `{name}.md` with the system prompt
3. Use it via: `spawn_agent(name="my-agent", template="{name}", task="...")`

Fields not set in the JSON file fall back to `default.json`, then `lyra.config.json`, then hardcoded defaults.

---

## Skills

Skills (reusable prompt templates) are stored separately in the `skills/` directory, not here. See `docs/CONFIGURATION_GUIDE.md` section 7 for the skill file format and usage. Agents can list skills via the `list_skills` tool and create new ones via `create_skill`.
