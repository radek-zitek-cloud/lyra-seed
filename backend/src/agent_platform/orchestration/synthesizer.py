"""Result synthesis — combines subtask results into a unified response."""

import logging

from agent_platform.llm.models import LLMConfig, Message, MessageRole
from agent_platform.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

_DEFAULT_PROMPT = (
    "You are a result synthesis engine. "
    "Combine the results from multiple subtasks "
    "into a single unified response that "
    "addresses the original task.\n\n"
    "Original task: {task}\n\n"
    "Subtask results:\n{results}\n\n"
    "Produce a clear, coherent response that "
    "integrates all the subtask outputs. "
    "Do not mention subtasks or orchestration "
    "- present the result as a unified answer."
)


class ResultSynthesizer:
    """Synthesizes multiple subtask results into a unified response."""

    def __init__(self, system_prompt: str | None = None) -> None:
        self._prompt = system_prompt or _DEFAULT_PROMPT

    async def synthesize(
        self,
        original_task: str,
        results: dict[str, str],
        llm: LLMProvider,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        results_text = "\n".join(
            f"- {subtask_id}: {result}" for subtask_id, result in results.items()
        )

        messages = [
            Message(
                role=MessageRole.SYSTEM,
                content=self._prompt.format(
                    task=original_task,
                    results=results_text,
                ),
            ),
            Message(
                role=MessageRole.HUMAN,
                content="Synthesize the above results into a unified response.",
            ),
        ]

        config = LLMConfig(temperature=temperature or 0.3)
        if model:
            config.model = model
        response = await llm.complete(messages, config=config)
        return response.content or ""
