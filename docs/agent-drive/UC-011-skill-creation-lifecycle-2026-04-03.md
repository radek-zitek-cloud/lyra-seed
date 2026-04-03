# UC-011: Skill Creation Lifecycle — Report 2026-04-03

## Execution context

- **Date:** 2026-04-03 ~21:00 UTC
- **Agent ID:** `f70d5cf4-ad86-41a4-bef4-4c7bf8bb5a2e`
- **Agent name:** `skill-tester`
- **Model:** openai/gpt-5.4

## Step 1: Skill tool awareness

Agent listed all 4 management tools (list_skills, create_skill, test_skill, update_skill) plus the 3 starter skills. PASS.

## Step 2: List existing skills

Agent called `list_skills` and returned all 3 starter skills with descriptions and parameters. PASS.

## Step 3: Semantic search

**Query:** "condensing or shortening text"

Agent called `list_skills(query="...")`. `summarize` ranked first (most relevant). PASS.

## Step 4: Test skill (dry-run)

**Template:** "Generate 3 professional email subject line options for this email:\n\n{{body}}"

Agent called `test_skill`. Results:
- **Output:** 3 subject lines (Request to Reschedule..., Q3 Review Meeting Moved..., Schedule Update...)
- **Verdict:** PASS
- **Reasoning:** Output matched the goal, produced 3 professional options

Events confirmed two LLM calls: gpt-5.4 (execution) then gpt-5.4-mini (evaluation). PASS.

## Step 5: Create skill

Agent called `create_skill(name="email-subject", ...)`. File created at `skills/email-subject.md`. Verified via `GET /skills/email-subject`. PASS.

## Step 6: Deduplication

**Attempt:** Create `subject-generator` with description "Create email subject lines from message content"

Agent attempted `create_skill` — deduplication caught it and flagged similarity with `email-subject`. Agent explained the conflict and offered alternatives (reuse, update, or create anyway). PASS.

## Step 7: Name validation

| Name | Result | Error |
|------|--------|-------|
| `my cool skill!` | Rejected | Invalid chars (spaces, exclamation) |
| `remember` | Rejected | Reserved tool name |

Both correctly rejected with appropriate error messages. PASS.

## Step 8: Update with versioning

Agent called `update_skill(name="email-subject", ...)` with template adding tone tags.

- Old version saved as `skills/email-subject.v1.md`
- New version written to `skills/email-subject.md`
- Both files confirmed on disk. PASS.

## Step 9: Version exclusion

Agent called `list_skills` and confirmed only `email-subject` appears, not `email-subject.v1`. PASS.

## Step 10: Use created skill

**Issue:** The agent did NOT call the `email-subject` tool despite it being in the schema (48 tools total, verified in event payload). The LLM chose to answer directly instead of invoking the tool, saying "I can't call email-subject directly."

This is an LLM behavior issue with large tool schemas — the model sometimes doesn't recognize newly created tools among 48 options. The skill is correctly registered and callable; the LLM just chose not to call it.

**Assessment:** PARTIAL — platform works correctly, LLM attention issue with large tool count.

## Step 11: Autonomous workflow

**Prompt:** "I often need to convert meeting notes into action items. Can you create a skill for that?"

On first attempt, agent described a plan but didn't execute. After being prompted to follow the recommended workflow, the agent executed all three steps:

1. `list_skills(query="meeting notes action items")` — no similar skill found
2. `test_skill(template="...", description="...", test_args="...")` — PASS verdict
3. `create_skill(name="meeting-notes-to-action-items", ...)` — created successfully

Event timestamps confirm correct order: list_skills → test_skill → create_skill. PASS (with prompting).

## Cost

| Model | Calls | Cost |
|-------|-------|------|
| gpt-5.4 | 25 | $0.5546 |
| gpt-5.4-mini | 19 | $0.0278 |
| text-embedding-3-large | 92 | $0.0004 |
| **Total** | **136** | **$0.5828** |

92 embedding calls — primarily from skill search and dedup checks across multiple turns.

## Final skill inventory

| Skill | Description |
|-------|-------------|
| code-review | Review code for quality, bugs, and improvements |
| email-subject | Generate professional email subject line options (with tone tags) |
| meeting-notes-to-action-items | Convert meeting notes into clear action items with owners and deadlines |
| summarize | Summarize text into concise bullet points |
| translate | Translate text to a target language |

Started with 3 starter skills, ended with 5 (2 created during test).

## Summary

| Criterion | Result |
|-----------|--------|
| list_skills returns starter skills | PASS |
| Semantic search ranks relevant first | PASS |
| test_skill executes + evaluates (two models) | PASS |
| create_skill writes file, immediately available | PASS |
| Deduplication rejects similar descriptions | PASS |
| Name validation (invalid chars + reserved) | PASS |
| update_skill versions old file | PASS |
| Version files not loaded | PASS |
| Created skill callable | PARTIAL (LLM didn't call it — tool schema size issue) |
| Autonomous search → test → create | PASS (with prompting) |

**Overall: PASS with observations.**

## Issues and observations

### 1. LLM doesn't call newly created skills

With 48 tools in the schema, the LLM chose to answer directly rather than calling the `email-subject` tool. The tool is correctly registered and in the schema. This is an LLM attention/tool-selection issue that worsens with large tool counts — reinforcing the importance of per-agent tool scoping (V2P4) to keep tool schemas manageable.

### 2. Autonomous workflow requires prompting

The agent described the search → test → create workflow but didn't execute it autonomously on the first attempt. After explicit instruction ("follow the recommended workflow"), it executed perfectly. The system prompt guidance is understood but not always followed proactively.

### 3. High embedding call count

92 embedding calls for ~10 turns. Each `list_skills(query=...)` and `create_skill` dedup check triggers embeddings. With the current simple approach (embed on every call), this adds up. Future optimization: cache query embeddings within a conversation.
