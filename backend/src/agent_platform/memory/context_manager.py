"""Context manager — assembles messages with memory injection and summarization."""

import logging

from agent_platform.llm.models import Message, MessageRole
from agent_platform.memory.chroma_memory_store import ChromaMemoryStore
from agent_platform.memory.models import MemoryEntry, MemoryType, MemoryVisibility
from agent_platform.memory.token_estimator import estimate_messages_tokens

logger = logging.getLogger(__name__)


class ContextManager:
    """Retrieves relevant memories and injects them into the conversation.

    When over token budget, summarizes old messages via LLM (if available)
    instead of just dropping them. Summaries are saved as EPISODIC memories.
    """

    def __init__(
        self,
        memory_store: ChromaMemoryStore,
        top_k: int = 5,
        max_context_tokens: int = 100_000,
        llm_provider: object | None = None,
        summary_model: str | None = None,
        event_bus: object | None = None,
        summary_prompt: str | None = None,
    ) -> None:
        self._store = memory_store
        self._top_k = top_k
        self._max_context_tokens = max_context_tokens
        self._llm = llm_provider
        self._summary_model = summary_model
        self._summary_prompt = summary_prompt
        self._event_bus = event_bus

    async def assemble(
        self,
        agent_id: str,
        messages: list[Message],
        query: str,
        top_k: int | None = None,
        max_context_tokens: int | None = None,
    ) -> list[Message]:
        """Assemble messages with memory injection and compression."""
        _top_k = top_k if top_k is not None else self._top_k
        _max_tokens = (
            max_context_tokens
            if max_context_tokens is not None
            else self._max_context_tokens
        )

        memories = await self._store.search(
            query=query,
            agent_id=agent_id,
            top_k=_top_k,
            include_public=True,
            exclude_archived=True,
        )

        # Remove any previous memory injection messages
        _MEMORY_PREFIX = "Relevant memories from previous interactions:"
        result = [
            m
            for m in messages
            if not (
                m.role == MessageRole.SYSTEM
                and isinstance(m.content, str)
                and m.content.startswith(_MEMORY_PREFIX)
            )
        ]

        if memories:
            for m in memories:
                await self._store.update_access(m.id)

            memory_lines = []
            for m in memories:
                prefix = f"[{m.memory_type.value}]"
                if m.agent_id != agent_id:
                    prefix += " [shared]"
                memory_lines.append(f"- {prefix} {m.content}")

            memory_text = _MEMORY_PREFIX + "\n" + "\n".join(memory_lines)

            memory_msg = Message(
                role=MessageRole.SYSTEM,
                content=memory_text,
            )

            # Insert after the first system message (system prompt)
            insert_idx = 0
            for i, msg in enumerate(result):
                if msg.role == MessageRole.SYSTEM:
                    insert_idx = i + 1
                    break

            result.insert(insert_idx, memory_msg)

        # Compress if over token budget
        return await self._compress(result, _max_tokens, agent_id)

    async def _compress(
        self,
        messages: list[Message],
        budget: int,
        agent_id: str,
    ) -> list[Message]:
        """Compress messages to fit within token budget.

        If LLM provider is configured, summarizes old messages.
        Otherwise falls back to simple truncation.
        """
        tokens = estimate_messages_tokens(messages)
        if tokens <= budget:
            return messages

        # Find messages to remove (oldest non-system, not the last)
        result = list(messages)
        to_summarize: list[Message] = []

        while estimate_messages_tokens(result) > budget and len(result) > 2:
            for i in range(len(result) - 1):
                if result[i].role != MessageRole.SYSTEM:
                    to_summarize.append(result.pop(i))
                    break
            else:
                break

        if not to_summarize:
            return result

        # Try LLM summarization
        if self._llm and self._summary_model:
            try:
                summary = await self._summarize_messages(to_summarize)
                # Save as EPISODIC memory
                entry = MemoryEntry(
                    agent_id=agent_id,
                    content=summary,
                    memory_type=MemoryType.EPISODIC,
                    importance=0.6,
                    visibility=MemoryVisibility.PRIVATE,
                )
                await self._store.add(entry)
                logger.info(
                    "Summarized %d messages into memory %s",
                    len(to_summarize),
                    entry.id,
                )
                # Emit events for observability
                if self._event_bus:
                    from agent_platform.observation.events import (
                        Event,
                        EventType,
                    )

                    await self._event_bus.emit(
                        Event(
                            agent_id=agent_id,
                            event_type=EventType.MEMORY_WRITE,
                            module="memory.summarizer",
                            payload={
                                "source": "context_summarization",
                                "memory_id": entry.id,
                                "messages_summarized": len(to_summarize),
                                "summary_preview": summary[:100],
                            },
                        )
                    )
                marker = f"[Summary of {len(to_summarize)} earlier messages: {summary}]"
            except Exception:
                logger.exception("Summarization failed, using truncation")
                marker = "[Earlier conversation history truncated for context limits]"
        else:
            marker = "[Earlier conversation history truncated for context limits]"

        # Insert marker after system messages
        marker_idx = 0
        for i, msg in enumerate(result):
            if msg.role == MessageRole.SYSTEM:
                marker_idx = i + 1
            else:
                break
        result.insert(
            marker_idx,
            Message(role=MessageRole.SYSTEM, content=marker),
        )

        return result

    async def _summarize_messages(self, messages: list[Message]) -> str:
        """Summarize messages using the configured LLM."""
        from agent_platform.memory.summarizer import ContextSummarizer

        summarizer = ContextSummarizer(
            llm_provider=self._llm,
            summary_model=self._summary_model,  # type: ignore[arg-type]
            system_prompt=self._summary_prompt,
        )
        return await summarizer.summarize(messages)
