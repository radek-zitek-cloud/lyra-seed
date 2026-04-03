# UC-011: Skill Creation Lifecycle

## Purpose

Validate the full skill self-evolution lifecycle: semantic search, dry-run testing with evaluation, skill creation with deduplication, skill updating with versioning, and autonomous skill discovery. Validates V3 Phase 1 deliverables.

## Preconditions

- Backend running at `http://localhost:8000` (restart after V3P1 merge)
- Starter skills loaded (summarize, translate, code-review)
- Clean DB recommended for clearer results

## Steps

### Step 1: Create agent and verify skill tools

```
POST /agents
{"name": "skill-tester"}
```

```
POST /agents/{id}/prompt
{"message": "What skill management tools do you have?"}
```

**Expected:** Agent describes list_skills, create_skill, test_skill, update_skill.

### Step 2: List existing skills

```
POST /agents/{id}/prompt
{"message": "Use list_skills to show me what skills are available."}
```

**Expected:** Agent calls `list_skills` and returns the 3 starter skills (summarize, translate, code-review) with descriptions and parameters.

### Step 3: Semantic skill search

```
POST /agents/{id}/prompt
{"message": "Search for skills related to condensing or shortening text. Use list_skills with a query."}
```

**Expected:** Agent calls `list_skills(query="condensing or shortening text")`. The `summarize` skill should rank first (most semantically similar).

### Step 4: Test a new skill before creating

```
POST /agents/{id}/prompt
{"message": "I want to create a skill that generates professional email subject lines from email body text. First, test it with test_skill using this template: 'Generate 3 professional email subject line options for this email:\n\n{{body}}' and test it with the body 'We need to reschedule the Q3 review meeting from Thursday to Friday due to a conflict with the board presentation.'"}
```

**Expected:**
- Agent calls `test_skill` with the template, description, and test_args
- Returns: output (3 subject line suggestions), verdict (PASS/FAIL), reasoning
- No skill file created yet

**Verify in events:**
- Two LLM calls: one for execution (agent's model), one for evaluation (orchestration model)

### Step 5: Create the skill after successful test

```
POST /agents/{id}/prompt
{"message": "The test passed. Now create the skill with name 'email-subject', description 'Generate professional email subject line options from email body text'."}
```

**Expected:**
- Agent calls `create_skill` with name, description, template, parameters
- Skill file created at `skills/email-subject.md`
- Skill immediately available

**Verify:**
```
GET /skills/email-subject
```
Should return the skill with its template.

### Step 6: Test deduplication

```
POST /agents/{id}/prompt
{"message": "Create a skill called 'subject-generator' with description 'Create email subject lines from message content'."}
```

**Expected:** `create_skill` rejects with error mentioning `email-subject` as a similar existing skill (semantic deduplication).

### Step 7: Test name validation

```
POST /agents/{id}/prompt
{"message": "Create a skill called 'my cool skill!' with template 'Do something'."}
```

**Expected:** Rejected — invalid name (space, exclamation mark).

```
POST /agents/{id}/prompt
{"message": "Create a skill called 'remember' with template 'Do something'."}
```

**Expected:** Rejected — reserved tool name.

### Step 8: Update an existing skill

```
POST /agents/{id}/prompt
{"message": "Update the email-subject skill to also suggest a tone tag (formal/casual/urgent) for each subject line. Use update_skill."}
```

**Expected:**
- Agent calls `update_skill` with name="email-subject" and updated template
- Old version saved as `skills/email-subject.v1.md`
- New version written to `skills/email-subject.md`

**Verify on disk:**
```bash
ls skills/email-subject*
```
Should show `email-subject.md` and `email-subject.v1.md`.

### Step 9: Verify version file not loaded

```
POST /agents/{id}/prompt
{"message": "Use list_skills to confirm only one email-subject skill exists, not the versioned one."}
```

**Expected:** Only `email-subject` in the list, not `email-subject.v1`.

### Step 10: Use the created skill

```
POST /agents/{id}/prompt
{"message": "Use the email-subject skill on this email body: 'Hi team, just a heads up that the deployment to production has been pushed to next Monday. The staging environment will remain frozen until then. Please hold all non-critical PRs.'"}
```

**Expected:** Agent calls the `email-subject` skill, gets subject line suggestions with tone tags (from the updated template).

### Step 11: Autonomous skill creation workflow

Test whether the agent follows the recommended search → test → create workflow without being told:

```
POST /agents/{id}/prompt
{"message": "I often need to convert meeting notes into action items. Can you create a skill for that?"}
```

**Expected:** Agent should:
1. Search for existing similar skills first (list_skills with query)
2. Test a template with test_skill
3. Create the skill after the test passes

**Check in events:** Whether the agent called list_skills, test_skill, and create_skill in that order.

### Step 12: Collect data

```
GET /agents/{id}/events
GET /agents/{id}/cost
GET /skills
```

## Success criteria

1. list_skills returns starter skills with descriptions
2. Semantic search ranks relevant skills first
3. test_skill executes template and returns PASS/FAIL verdict
4. test_skill uses two LLM calls (execution + evaluation with different models)
5. create_skill writes file and skill is immediately available
6. Deduplication rejects semantically similar descriptions
7. Name validation rejects invalid chars and reserved names
8. update_skill versions the old file and writes new content
9. Version files not loaded as active skills
10. Created skill is callable and produces correct output
11. Agent follows search → test → create workflow autonomously

## What to report

- Skill search results and ranking
- test_skill output, verdict, and reasoning
- Deduplication rejection message (which existing skill was flagged)
- Version files created on disk
- Model usage: which model for execution vs evaluation
- Whether the agent followed the recommended workflow autonomously
- Cost breakdown by model
- Any unexpected behavior
