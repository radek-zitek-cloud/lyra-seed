"""Task decomposition — breaks complex tasks into subtasks using LLM."""

import json
import logging

from agent_platform.llm.models import LLMConfig, Message, MessageRole
from agent_platform.llm.provider import LLMProvider
from agent_platform.orchestration.models import (
    FailurePolicy,
    OrchestrationStrategyType,
    SubTask,
    TaskPlan,
)
from agent_platform.tools.models import Tool

logger = logging.getLogger(__name__)

_DEFAULT_PROMPT = (
    "You are a task decomposition engine. "
    "Break the given task into subtasks.\n\n"
    "Available tools: {tools}\n\n"
    "Respond with ONLY valid JSON "
    "(no markdown, no explanation) in this format:\n"
    '{{\n  "subtasks": [\n    {{\n'
    '      "description": "What this subtask does",\n'
    '      "assigned_to": "spawn_agent",\n'
    '      "dependencies": [],\n'
    '      "failure_policy": "escalate"\n'
    "    }}\n  ],\n"
    '  "strategy": "sequential"\n}}\n\n'
    "Rules:\n"
    '- "assigned_to" should be "spawn_agent" for '
    "complex work, or a tool name for simple ops\n"
    '- "dependencies" is a list of zero-indexed '
    "subtask positions this subtask depends on\n"
    '- "failure_policy" is one of: '
    '"retry", "reassign", "escalate", "skip"\n'
    '- "strategy" is one of: "sequential" (ordered),'
    ' "parallel" (independent), "pipeline" (chain)\n'
    "- If subtasks have dependencies, "
    'use "sequential" or "pipeline"\n'
    "- If subtasks are independent, "
    'use "parallel"'
)


class TaskDecomposer:
    """Decomposes complex tasks into subtask plans using LLM."""

    def __init__(self, system_prompt: str | None = None) -> None:
        self._prompt = system_prompt or _DEFAULT_PROMPT

    async def decompose(
        self,
        task: str,
        available_tools: list[Tool],
        llm: LLMProvider,
        model: str | None = None,
        max_subtasks: int = 10,
        temperature: float | None = None,
    ) -> TaskPlan:
        tool_descriptions = ", ".join(
            f"{t.name}: {t.description}" for t in available_tools
        )

        messages = [
            Message(
                role=MessageRole.SYSTEM,
                content=self._prompt.format(tools=tool_descriptions),
            ),
            Message(
                role=MessageRole.HUMAN,
                content=f"Decompose this task: {task}",
            ),
        ]

        config = LLMConfig(temperature=temperature or 0.3)
        if model:
            config.model = model
        response = await llm.complete(messages, config=config)

        content = response.content or "{}"
        # Strip markdown code fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            content = (
                "\n".join(lines[1:-1])
                if lines[-1].strip() == "```"
                else "\n".join(lines[1:])
            )

        data = json.loads(content)

        subtasks = []
        raw_subtasks = data.get("subtasks", [])[:max_subtasks]
        for i, st_data in enumerate(raw_subtasks):
            policy_str = st_data.get("failure_policy", "escalate")
            subtasks.append(
                SubTask(
                    description=st_data["description"],
                    assigned_to=st_data.get("assigned_to", "spawn_agent"),
                    dependencies=st_data.get("dependencies", []),
                    failure_policy=FailurePolicy(policy_str),
                )
            )

        strategy_str = data.get("strategy", "sequential")
        strategy = OrchestrationStrategyType(strategy_str)

        return TaskPlan(
            original_task=task,
            subtasks=subtasks,
            strategy=strategy,
        )
