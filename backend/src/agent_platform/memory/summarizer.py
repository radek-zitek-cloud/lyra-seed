"""Context summarizer — LLM-based conversation summarization."""

import logging

from agent_platform.llm.models import LLMConfig, Message, MessageRole

logger = logging.getLogger(__name__)

DEFAULT_SUMMARY_PROMPT = (
    "Summarize the following conversation concisely in 2-4 sentences. "
    "Focus on key topics, decisions, and outcomes."
)


class ContextSummarizer:
    """Summarizes conversation messages using an LLM."""

    def __init__(
        self,
        llm_provider: object,
        summary_model: str,
        system_prompt: str | None = None,
    ) -> None:
        self._llm = llm_provider
        self._model = summary_model
        self._system_prompt = system_prompt or DEFAULT_SUMMARY_PROMPT

    async def summarize(self, messages: list[Message]) -> str:
        """Summarize a list of messages into a concise text."""
        # Build the conversation text for summarization
        conversation_text = "\n".join(
            f"{msg.role}: {msg.content}"
            for msg in messages
            if isinstance(msg.content, str) and msg.content.strip()
        )

        llm_messages = [
            Message(role=MessageRole.SYSTEM, content=self._system_prompt),
            Message(role=MessageRole.HUMAN, content=conversation_text),
        ]

        config = LLMConfig(model=self._model, temperature=0.0)
        response = await self._llm.complete(llm_messages, config=config)
        return response.content or "No summary generated."
