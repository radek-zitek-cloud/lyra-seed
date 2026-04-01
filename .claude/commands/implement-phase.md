Implement a project phase. The argument is the phase identifier (e.g., `v1-phase-0`, `v1-phase-1`).

**Phase to implement:** $ARGUMENTS

## Instructions

Follow the development methodology defined in this project. Execute these steps in order:

### Step 1: Read Project Documentation

Read these files before doing anything else:

1. `METHODOLOGY.md` — The development workflow you must follow
2. `ROADMAP.md` — Find the section for phase `$ARGUMENTS`, extract deliverables and exit criteria
3. `REQUIREMENTS.md` — Understand the overall project requirements

### Step 2: Check Prerequisites

- Look at `docs/phases/` for any prior phases
- If prior phases exist, read their `STATUS.md` to confirm they are `COMPLETE`
- If a prerequisite phase is not complete, **stop and inform the human**

### Step 3: Git — Prepare Branch

1. Switch to `master` branch: `git checkout master`
2. Check working tree status: `git status`
3. If there are uncommitted changes, commit them: `git add -A && git commit -m "WIP: uncommitted changes before $ARGUMENTS"`
4. Pull latest if remote exists: `git pull --ff-only || true`
5. Create and switch to the phase branch: `git checkout -b $ARGUMENTS`

The branch name is the phase identifier (e.g., `v1-phase-0`).

### Step 4: Generate Plan & Smoke Tests

Create `docs/phases/$ARGUMENTS/` with three files following the templates in METHODOLOGY.md:

1. `PLAN.md` — Implementation plan with steps, file manifest, dependencies
2. `SMOKE_TESTS.md` — Human-readable smoke test specifications
3. `STATUS.md` — Initialize as `NOT STARTED`

Commit the plan: `git add docs/phases/$ARGUMENTS/ && git commit -m "$ARGUMENTS: add plan and smoke test specs"`

**Present the PLAN.md and SMOKE_TESTS.md to the human and wait for approval before proceeding.**

### Step 5: Implement Smoke Tests First

Create the automated smoke test file(s) based on SMOKE_TESTS.md:
- Backend: `backend/tests/smoke/test_{phase_id}.py` (replace hyphens with underscores)
- Frontend (if applicable): `frontend/tests/smoke/smoke.{phase_id}.spec.ts`

Run the smoke tests — they should all **fail** at this point (tests exist, code doesn't yet). This confirms the harness works.

Commit the test files: `git add -A && git commit -m "$ARGUMENTS: add smoke test harness"`

### Step 6: Implementation Loop

```
while not all_smoke_tests_pass:
    implement_next_deliverable()
    git add -A && git commit -m "$ARGUMENTS: <describe what was implemented>"
    run_smoke_tests()
    if failures:
        analyze_failure_output()
        fix_code()
        git add -A && git commit -m "$ARGUMENTS: fix <describe what was fixed>"
    update STATUS.md with current iteration results
```

Run smoke tests using: `cd backend && uv run pytest tests/smoke/ -k "{phase_id}" -v --tb=short`

Commit after each meaningful deliverable or fix — keep commits granular and descriptive.

### Step 7: Completion

1. Run the full smoke test suite one final time — all tests for this phase must pass
2. Run `just lint` and `just format` — fix any issues, commit if changes were made
3. If prior phases exist, run their smoke tests too to confirm no regressions
4. Update `STATUS.md` to `COMPLETE` with final test results and iteration log
5. Commit final status: `git add -A && git commit -m "$ARGUMENTS: phase complete — all smoke tests pass"`

### Step 8: Git — Merge to Master

1. Switch to master: `git checkout master`
2. Merge the phase branch: `git merge $ARGUMENTS --no-ff -m "Merge $ARGUMENTS: <phase title from roadmap>"`
3. **Do not delete the branch** — keep it for history: the branch `$ARGUMENTS` remains
4. Verify on master: run the smoke tests once more to confirm the merge is clean

## Critical Rules

- **Never declare a phase complete without passing smoke tests.** The tests are the sole authority.
- **Never skip the human review gate** after generating the plan and smoke tests.
- **All work happens on the phase branch**, never directly on master.
- **Commit frequently** with descriptive messages prefixed by the phase identifier.
- **All code must work cross-platform** (Linux bash + Windows PowerShell).
- **LLM and external API calls are always mocked** in smoke tests.
- **Update STATUS.md** after every iteration, not just at the end.
- **Never delete the phase branch** after merging.