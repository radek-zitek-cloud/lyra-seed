"""Result synthesis — combines subtask results into a unified response."""

import logging

from agent_platform.llm.models import LLMConfig, Message, MessageRole
from agent_platform.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = (
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

    async def synthesize(
        self,
        original_task: str,
        results: dict[str, str],
        llm: LLMProvider,
    ) -> str:
        results_text = "\n".join(
            f"- {subtask_id}: {result}" for subtask_id, result in results.items()
        )

        messages = [
            Message(
                role=MessageRole.SYSTEM,
                content=SYNTHESIS_PROMPT.format(
                    task=original_task,
                    results=results_text,
                ),
            ),
            Message(
                role=MessageRole.HUMAN,
                content="Synthesize the above results into a unified response.",
            ),
        ]

        response = await llm.complete(messages, config=LLMConfig(temperature=0.3))
        return response.content or ""
