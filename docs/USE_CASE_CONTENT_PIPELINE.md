# Use Case: Technical Content Pipeline

A concrete, real-world application of the Lyra Agent Platform — turning technical knowledge into publishable content for a software consultancy or dev team.

---

## The Problem

A small tech team or consultancy needs to regularly produce:
- Blog posts about technologies they use
- Technical decision documents (ADRs)
- Client-facing summaries of technical work
- Translated content for international clients

This is tedious, takes senior engineers away from engineering, and the quality is inconsistent. Currently it's either "nobody writes" or "one person writes everything."

## The Setup

### MCP Servers

Already configured — `filesystem` for reading/writing content and `shell` for running commands (e.g., `git log` to pull recent work, `curl` to fetch API docs).

### Skills

```
skills/
├── executive-summary.md      # Condense technical content into business-friendly summary
├── swot-analysis.md           # Produce SWOT analysis from research findings
├── adr-template.md            # Generate Architecture Decision Record from context
├── blog-outline.md            # Create a blog post outline from a topic + research
├── seo-metadata.md            # Generate title, description, keywords for a post
├── changelog-entry.md         # Turn git log into a human-readable changelog entry
```

Each is a reusable prompt template the agent creates once and uses repeatedly. As the team discovers more patterns ("we always need a TL;DR at the top"), agents create new skills.

### Agent Templates

```
prompts/
├── content-coordinator.json/md    # Orchestrates the full pipeline
├── tech-researcher.json/md        # Deep-dives into a technology topic
├── blog-writer.json/md            # Writes engaging technical blog posts
├── adr-writer.json/md             # Writes Architecture Decision Records
├── translator.json/md             # Professional technical translation
```

**content-coordinator** — the main agent. Receives requests like "write a blog post about our migration from REST to gRPC." Searches for relevant templates, spawns the right sub-agents, orchestrates the pipeline, uses skills for recurring patterns.

**tech-researcher** — scoped to filesystem + shell. Reads the codebase (`git log`, source files, READMEs), searches for relevant memories from past research, produces structured findings. `allowed_mcp_servers: ["filesystem", "shell"]`.

**blog-writer** — pure reasoning, no tools. Takes research as input, produces an engaging blog post with code examples. Higher temperature (0.8) for creative writing. `allowed_mcp_servers: []`.

**adr-writer** — pure reasoning. Takes a technical decision context and produces a structured ADR (Context, Decision, Consequences). Low temperature (0.3) for precision. `allowed_mcp_servers: []`.

**translator** — pure reasoning. Professional technical translation preserving code blocks and terminology. Uses the existing `translate` skill or direct prompting. `allowed_mcp_servers: []`.

## The Flow

```
User: "Write a blog post about how we implemented real-time 
       event streaming with SSE in the Lyra platform."

content-coordinator:
  1. list_templates(query="research") → finds tech-researcher
  2. list_templates(query="blog writing") → finds blog-writer
  3. recall(query="SSE implementation") → checks existing knowledge
  4. spawn_agent(template="tech-researcher", task="Research the SSE 
     implementation in lyra-seed: read backend/src/agent_platform/api/ws_routes.py,
     the event bus, and how the frontend consumes the stream...")
  5. wait_for_agent → gets structured research
  6. spawn_agent(template="blog-writer", task="Write a technical blog post 
     based on this research: {research}. Target audience: mid-level developers.
     Include code snippets.")
  7. wait_for_agent → gets draft
  8. spawn_agent(template="critic", task="Review this blog post for 
     technical accuracy and readability: {draft}")
  9. Use executive-summary skill for TL;DR
  10. Use seo-metadata skill for SEO
  11. Write final post to work/blog/sse-streaming.md
  12. Optionally: spawn translator for French/Czech versions
```

## What Makes This Actually Useful

**It reads your actual code.** The researcher agent uses filesystem and shell tools to read the real implementation, not hallucinate about it. `git log --oneline -20 backend/src/agent_platform/api/ws_routes.py` gives real commit history. The blog post references actual code.

**Memory accumulates.** After researching SSE, the platform stores facts about the implementation. Next time someone asks about "real-time updates" or "event streaming," the knowledge is already there — no re-research needed.

**Skills compound.** The first time the coordinator needs an executive summary, it creates the skill. The second time, it finds it via `list_skills(query="summary")`. Over time the pipeline gets faster.

**Quality gates.** The critic template catches "this code example is incomplete" or "the audience section is too advanced for mid-level developers" before the post is published.

**Consistent output.** Every blog post gets the same structure: TL;DR, context, implementation deep-dive, code snippets, takeaways, SEO metadata. The skills enforce this without human oversight.

## What You'd Need to Build

1. **5 skill files** — ~30 minutes of prompt writing
2. **5 template files** — ~45 minutes (the prompts need care, especially the coordinator)
3. **A `work/blog/` output directory** — already exists pattern from the coder template
4. **Nothing else** — the platform, tools, orchestration, and discovery are already built

## What It Doesn't Do (Yet)

- Can't publish to a CMS (would need a CMS MCP server — exactly what V3P2 is about)
- Can't fetch live web content (would need a web search/scrape MCP server)
- Can't generate diagrams (would need a diagram MCP server)
- Researcher can only read files the filesystem MCP server can access

These are all solvable with additional MCP servers — which is exactly the V3P2 roadmap item.
