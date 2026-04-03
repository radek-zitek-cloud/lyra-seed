# V2 Phase 3 — Smoke Tests

## Test Environment
- Prerequisites: V2P2 complete, all prior smoke tests passing
- LLM calls: always mocked
- External APIs: never called

## Backend Smoke Tests

### ST-V2-3.1: Orchestration models exist with correct fields
- **Validates:** Data models
- **Checks:**
  - SubTask has: id, description, assigned_to, dependencies, status, result, failure_policy
  - TaskPlan has: id, original_task, subtasks, strategy, status
  - SubTaskStatus enum has: PENDING, RUNNING, COMPLETED, FAILED, SKIPPED
  - OrchestrationStrategyType enum has: SEQUENTIAL, PARALLEL, PIPELINE
  - FailurePolicy enum has: RETRY, REASSIGN, ESCALATE, SKIP
  - OrchestrationResult has: plan_id, results, synthesized_response, status

### ST-V2-3.2: Task decomposition produces a valid plan
- **Validates:** TaskDecomposer decomposes a task into subtasks
- **Method:** Mock LLM to return a structured decomposition JSON
- **Checks:**
  - Returns a TaskPlan with subtasks
  - Each subtask has description and assigned_to
  - Strategy is set (sequential, parallel, or pipeline)
  - All subtasks start as PENDING

### ST-V2-3.3: Sequential orchestration runs subtasks in order
- **Validates:** SequentialOrchestration strategy
- **Method:** Create a plan with 3 sequential subtasks, mock tool/agent execution
- **Checks:**
  - Subtasks execute in order (1 then 2 then 3)
  - Each subtask receives the correct input
  - All subtask statuses update to COMPLETED
  - OrchestrationResult contains all subtask results

### ST-V2-3.4: Parallel orchestration runs independent subtasks concurrently
- **Validates:** ParallelOrchestration strategy
- **Method:** Create a plan with 3 independent subtasks
- **Checks:**
  - All subtasks start execution (all reach RUNNING)
  - All subtasks complete
  - Results collected from all subtasks
  - Total time roughly equal to longest subtask (not sum)

### ST-V2-3.5: Pipeline orchestration chains output to input
- **Validates:** PipelineOrchestration strategy
- **Method:** Create a plan with 3 pipeline subtasks
- **Checks:**
  - Subtask 1 runs and produces output
  - Subtask 2 receives subtask 1's output as context
  - Subtask 3 receives subtask 2's output as context
  - Final result includes the pipeline chain

### ST-V2-3.6: Result synthesis combines subtask outputs
- **Validates:** ResultSynthesizer
- **Method:** Mock LLM to produce a synthesis from multiple results
- **Checks:**
  - Receives all subtask results and original task
  - Returns a unified synthesized response string
  - LLM called with correct prompt containing all results

### ST-V2-3.7: Failure policy RETRY retries failed subtask
- **Validates:** Retry failure handling
- **Method:** Subtask fails on first attempt, succeeds on retry
- **Checks:**
  - Subtask retried after failure
  - Succeeds on second attempt
  - Final status is COMPLETED

### ST-V2-3.8: Failure policy SKIP skips failed subtask
- **Validates:** Skip failure handling
- **Method:** Subtask fails with SKIP policy
- **Checks:**
  - Failed subtask marked as SKIPPED
  - Remaining subtasks continue executing
  - OrchestrationResult still returned (partial)

### ST-V2-3.9: Failure policy ESCALATE stops orchestration
- **Validates:** Escalate failure handling
- **Method:** Subtask fails with ESCALATE policy
- **Checks:**
  - Orchestration stops immediately
  - Error information returned with context
  - Remaining subtasks not executed

### ST-V2-3.10: decompose_task tool is callable via ToolRegistry
- **Validates:** Tool integration
- **Method:** Register OrchestrationToolProvider, call decompose_task
- **Checks:**
  - Tool appears in registry's tool list
  - Tool can be called with a task description
  - Returns a valid TaskPlan as ToolResult

### ST-V2-3.11: orchestrate tool runs end-to-end
- **Validates:** Full orchestration pipeline
- **Method:** Mock LLM for decomposition, execution, and synthesis
- **Checks:**
  - Tool decomposes the task
  - Executes subtasks per chosen strategy
  - Synthesizes results
  - Returns unified response as ToolResult

### ST-V2-3.12: Orchestration emits events
- **Validates:** Observability
- **Method:** Run orchestration, query event bus
- **Checks:**
  - Events emitted for plan creation
  - Events emitted for each subtask execution
  - Events emitted for synthesis
