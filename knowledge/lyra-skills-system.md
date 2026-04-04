# Lyra Skills System

## What Are Skills

Skills are reusable prompt templates stored as .md files. They register as tools that agents can call. When invoked, the platform expands the template with provided arguments and makes an LLM sub-call to produce the result.

## Skill File Format

Each skill is a .md file in the skills/ directory with YAML frontmatter:

```markdown
---
name: summarize
description: Summarize text into concise bullet points
parameters:
  text:
    type: string
    description: The text to summarize
    required: true
  bullet_count:
    type: string
    description: Number of bullet points
---

Summarize the following text into {{bullet_count}} concise bullet points.

{{text}}
```

The frontmatter defines the tool schema. The body is the template with `{{parameter}}` placeholders.

## Skill Management Tools

### list_skills

List available skills. Supports semantic search:
- `list_skills()` — all skills
- `list_skills(query="text summarization")` — ranked by relevance

### create_skill

Create a new skill file. The platform:
- Validates the name (alphanumeric, hyphens, underscores)
- Rejects reserved tool names (remember, spawn_agent, etc.)
- Checks for semantic duplicates (rejects if > 0.85 similarity to existing)
- Writes the .md file
- Makes it immediately available

### test_skill

Dry-run a template before creating. Two LLM calls:
1. Execution: expand template with test arguments, get output
2. Evaluation: assess whether output matches the description (PASS/FAIL with reasoning)

Uses the agent's model for execution, orchestration model for evaluation.

### update_skill

Update an existing skill. The old version is preserved as `{name}.v{n}.md` (e.g., `summarize.v1.md`). Version files are retained but not loaded as active skills.

## Built-in Skills

Three starter skills ship with the platform:

### summarize

Summarize text into concise bullet points. Parameters: text, bullet_count.

### translate

Translate text to a target language. Parameters: text, language.

### code-review

Review code for quality, bugs, and improvements. Parameters: code, language, focus.

## Skill Discovery

Agents find skills via:
- `list_skills(query="...")` — semantic search over descriptions
- `discover(query="...")` — unified search across all capabilities
- Tool list — skills appear alongside all other tools

## Recommended Workflow

1. **Search** — `list_skills(query="...")` to check if similar skill exists
2. **Test** — `test_skill(template, description, test_args)` to validate quality
3. **Create** — `create_skill(name, template, description)` after test passes
4. **Use** — call the skill by name like any other tool

## Skill Execution

When a skill is called:
1. Template placeholders replaced with provided arguments
2. Expanded prompt sent as a single LLM call
3. Uses the calling agent's configured model
4. Result returned as tool output

## Configuration

- `skillsDir` in lyra.config.json (default: ./skills)
- Skills reload on server restart or via /config/reload
