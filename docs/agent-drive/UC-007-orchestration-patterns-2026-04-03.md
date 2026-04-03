# UC-007: Orchestration Patterns — Report 2026-04-03

## Execution context

- **Date:** 2026-04-03 16:35 UTC
- **Agent ID:** `00ef23c9-932d-4453-8cfd-5e610c69da19`
- **Agent name:** `orchestrator`
- **Model:** openai/gpt-5.4
- **Orchestration model:** openai/gpt-5.4-mini
- **Max subtasks:** 10

## Step 2: Decompose only

**Prompt:** "Use decompose_task to break down this task: Design a company offsite event..."

**Result:** 5 subtasks, sequential strategy. Topics: venue selection, activity planning, catering, travel logistics, budget estimation.

| Check | Result |
|-------|--------|
| Agent called decompose_task | PASS |
| No execution occurred | PASS |
| No synthesis subtask in plan | PASS |
| Decomposition used orchestrationModel (gpt-5.4-mini) | PASS |
| Agent reasoning used main model (gpt-5.4) | PASS |

## Step 3: Parallel orchestration

**First attempt:** "Compare TypeScript, Kotlin, and Swift..." — agent answered directly without orchestration. It judged a 3-language comparison as simple enough for a single LLM call. Reasonable but didn't test parallel.

**Second attempt (explicit):** "Use orchestrate with parallel strategy to produce a detailed market analysis covering cloud infrastructure, container orchestration, observability platforms, and edge computing."

**Result:** 5 subtasks, parallel strategy. All 5 subtask `tool_call` events at `16:36:30` (same second).

| Subtask | Start | Complete | Duration |
|---------|-------|----------|----------|
| Cloud infrastructure | 16:36:30 | 16:36:52 | 22s |
| Container orchestration | 16:36:30 | 16:36:52 | 22s |
| Observability platforms | 16:36:30 | 16:36:51 | 21s |
| Edge computing | 16:36:30 | 16:36:51 | 21s |
| Synthesis subtask (!) | 16:36:30 | 16:36:31 | 1s |

**Note:** The decomposer created a 5th "synthesize" subtask that completed in 1s with minimal output. The platform's ResultSynthesizer then ran separately and produced the actual unified response (16:36:52–16:37:06, 14s). The prompt improvement from earlier testing reduced but did not fully eliminate synthesis subtasks.

| Check | Result |
|-------|--------|
| Parallel execution (same-second timestamps) | PASS |
| All orchestration calls used gpt-5.4-mini | PASS |
| ResultSynthesizer produced unified response | PASS |
| No synthesis subtask in plan | FAIL (1 appeared) |

## Step 4: Pipeline orchestration

**Prompt:** "Orchestrate with pipeline strategy: brainstorm ideas → evaluate → elevator pitch"

**Result:** 3 subtasks, pipeline strategy. Sequential execution with context chaining.

| Subtask | Start | Complete | Duration |
|---------|-------|----------|----------|
| Brainstorm 5 ideas | 16:38:04 | 16:38:10 | 6s |
| Evaluate and pick best | 16:38:10 | 16:38:19 | 9s |
| Write elevator pitch | 16:38:19 | 16:38:22 | 3s |

**Context chaining verified:** Step 2 evaluated the specific ideas from Step 1. Step 3 wrote a pitch for the winner selected in Step 2. The output was coherent — the elevator pitch referenced "AI Dev Workflow Copilot" which was brainstormed in Step 1 and selected in Step 2.

| Check | Result |
|-------|--------|
| Sequential timestamps | PASS |
| Context chaining (output → next input) | PASS |
| Coherent final output | PASS |

## Step 5: Sequential orchestration

**Prompt:** "Orchestrate with sequential strategy: define microservices → list anti-patterns → suggest mitigations"

**Result:** 3 subtasks, sequential strategy.

| Subtask | Start | Complete | Duration |
|---------|-------|----------|----------|
| Define microservice architecture | 16:39:12 | 16:39:15 | 3s |
| List 5 anti-patterns | 16:39:15 | 16:39:18 | 3s |
| Suggest mitigations | 16:39:18 | 16:39:20 | 2s |

| Check | Result |
|-------|--------|
| Sequential timestamps | PASS |
| Each subtask self-contained | PASS |
| Unified synthesized response | PASS |

## Step 6: Autonomous strategy selection

**Two prompts tested without mentioning any tool or strategy:**

1. "Security audit checklist covering 5 topics" — agent answered directly (3 events, no orchestration)
2. "Comprehensive fintech due diligence report covering 5 areas" — agent answered directly (3 events, no orchestration)

**Assessment:** The agent's threshold for "worth orchestrating" is higher than expected. It prefers to answer complex knowledge questions directly rather than incur orchestration overhead. This is defensible behavior — the system prompt says "For simple tasks you can answer directly — orchestration adds overhead" and the agent interprets these as answerable in a single pass.

**To reliably trigger autonomous orchestration**, the task would need to be either:
- Explicitly multi-step (pipeline-shaped)
- So broad that a single LLM call would produce shallow results
- Requiring different strategies for different parts

| Check | Result |
|-------|--------|
| Agent can autonomously choose orchestrate | INCONCLUSIVE — agent preferred direct answers |

## Step 7: orchestrationModel verification

| Purpose | Model used | Count |
|---------|-----------|-------|
| Agent reasoning (tool decisions, presenting results) | gpt-5.4 | 13 calls |
| Orchestration (decomposition, subtasks, synthesis) | gpt-5.4-mini | 25 calls |
| Fact extraction | gpt-5.4-mini | (included in above) |
| Embeddings | text-embedding-3-large | 56 calls |

**No minimax calls.** The orchestrationModel config is working correctly.

| Check | Result |
|-------|--------|
| Orchestration uses orchestrationModel | PASS |
| Agent reasoning uses main model | PASS |
| No fallback to LLMConfig default (minimax) | PASS |

## Step 8: maxSubtasks cap

**Prompt:** "Use decompose_task to plan a complete wedding" — listed 20 items.

**Result:** Plan returned exactly 10 subtasks (parallel strategy). Cap enforced.

| Check | Result |
|-------|--------|
| maxSubtasks=10 enforced | PASS (20 requested, 10 returned) |

## Cost

| Model | Calls | Cost |
|-------|-------|------|
| gpt-5.4 | 13 | $0.9971 |
| gpt-5.4-mini | 25 | $0.1772 |
| text-embedding-3-large | 56 | $0.0003 |
| **Total** | **94** | **$1.1745** |

**Observation:** gpt-5.4 accounts for 85% of cost despite only 13 calls (vs 25 for gpt-5.4-mini). This validates the orchestrationModel config — without it, all 25 orchestration calls would have used gpt-5.4 at ~5x the cost.

## Summary

| Criterion | Result |
|-----------|--------|
| decompose_task returns valid plan | PASS |
| Parallel: concurrent execution | PASS |
| Pipeline: context chaining | PASS |
| Sequential: ordered execution | PASS |
| Autonomous tool selection | INCONCLUSIVE |
| No synthesis subtask in plans | PARTIAL (1 appeared in parallel test) |
| orchestrationModel used correctly | PASS |
| maxSubtasks cap enforced | PASS |
| ResultSynthesizer produces coherent output | PASS |
| Orchestration events emitted | PASS |

**Overall: PASS with notes.**

## Issues and observations

### 1. Synthesis subtask still appears occasionally

Despite the decomposer prompt prohibiting synthesis subtasks, one appeared in the parallel test (Step 3). It completed in 1s with minimal output and was effectively ignored by the platform's ResultSynthesizer. The prompt improvement reduced but didn't eliminate the pattern. May need stronger prompt language or post-parse filtering.

### 2. Autonomous orchestration threshold is high

The agent prefers to answer complex knowledge questions directly rather than orchestrate. This is arguably correct behavior (lower latency, lower cost) but means the `orchestrate` tool may only be used when explicitly requested or when the task is extremely broad. Consider whether the system prompt guidance should lower the threshold.

### 3. Cost savings from orchestrationModel are significant

25 orchestration calls at gpt-5.4-mini cost $0.18 vs an estimated $0.90+ if they'd used gpt-5.4. The config saves ~80% on orchestration LLM costs.
