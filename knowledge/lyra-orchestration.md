# Lyra Orchestration System

## Overview

Orchestration enables agents to decompose complex tasks into subtasks and execute them using one of three strategies. The platform handles decomposition, execution, failure recovery, and result synthesis automatically.

## Tools

### decompose_task

Breaks a task into a structured plan without executing it. The LLM analyzes the task and produces subtasks with dependencies, strategies, and failure policies.

Use this when you want to show the user a plan before committing to execution.

### orchestrate

End-to-end orchestration: decompose → execute → synthesize. One tool call handles everything.

Parameters:
- task (required): the complex task to orchestrate
- strategy (optional): force sequential, parallel, or pipeline

## Execution Strategies

### Sequential

Subtasks run one after another in order. Each subtask starts after the previous completes.

Best for: tasks with dependencies between steps, ordered workflows.

### Parallel

Independent subtasks run concurrently via asyncio. All start at the same time, results collected when all complete.

Best for: tasks with unrelated parts that can be done simultaneously. Example: researching 4 different companies — each is independent.

### Pipeline

Each subtask's output feeds into the next as context. Subtask 2 receives subtask 1's output, subtask 3 receives subtask 2's output.

Best for: multi-stage processing where each step builds on the previous. Example: brainstorm → evaluate → write pitch.

## Failure Policies

Each subtask has a failure policy:

| Policy | Behavior |
|--------|----------|
| escalate | Stop orchestration, return error (default) |
| retry | Retry the subtask (up to 2 attempts) |
| skip | Mark as skipped, continue with remaining |
| reassign | Re-execute with fresh attempt |

## Important Limitations

Orchestrated subtasks execute as standalone LLM calls. They do NOT have access to tools (filesystem, shell, memory). They can only reason and produce text.

If a subtask needs tool access, use spawn_agent directly instead of orchestrate.

## Configuration

- `orchestrationModel`: cheaper model for subtask LLM calls (e.g., gpt-5.4-mini)
- `maxSubtasks`: maximum subtasks per decomposition (default: 10)

The orchestration model is separate from the agent's main reasoning model. This saves cost — subtask execution doesn't need the full model.

## Decomposition Prompt

The decomposition prompt is externalized at `prompts/system/decompose_task.md`. It instructs the LLM to:
- Break the task into subtasks with descriptions
- Choose the right strategy (parallel, sequential, pipeline)
- NOT include a synthesis subtask (the platform handles synthesis automatically)
- Ensure parallel subtasks are truly independent

## Result Synthesis

After all subtasks complete, the ResultSynthesizer combines all outputs into a unified response using a separate LLM call. The synthesis prompt is at `prompts/system/synthesize_results.md`.

## When to Use Orchestration

Good fit:
- Tasks with 3+ distinct parts
- Independent topics that benefit from parallel execution
- Pipeline workflows where each step transforms the output
- When you want automatic failure recovery

Not a good fit:
- Simple tasks answerable in one LLM call
- Tasks with 1-2 steps
- Interactive step-by-step work
- When subtasks need tool access

## Patterns

Use `store_pattern` to save successful orchestration approaches. Use `find_pattern` to search for reusable patterns before decomposing a new task from scratch.
