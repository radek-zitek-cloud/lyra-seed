"""Context manager — assembles messages with memory injection and truncation."""

from agent_platform.llm.models import Message, MessageRole
from agent_platform.memory.chroma_memory_store import ChromaMemoryStore
from agent_platform.memory.token_estimator import estimate_messages_tokens


class ContextManager:
    """Retrieves relevant memories and injects them into the conversation.

    Also enforces a token budget by truncating old messages when needed.
    """

    def __init__(
        self,
        memory_store: ChromaMemoryStore,
        top_k: int = 5,
        max_context_tokens: int = 100_000,
    ) -> None:
        self._store = memory_store
        self._top_k = top_k
        self._max_context_tokens = max_context_tokens

    async def assemble(
        self,
        agent_id: str,
        messages: list[Message],
        query: str,
        top_k: int | None = None,
        max_context_tokens: int | None = None,
    ) -> list[Message]:
        """Assemble messages with memory injection and truncation.

        Per-call overrides take precedence over constructor defaults.
        """
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
        )

        if not memories:
            result = list(messages)
        else:
            # Update access timestamps
            for m in memories:
                await self._store.update_access(m.id)

            # Build memory injection message
            memory_lines = []
            for m in memories:
                memory_lines.append(f"- [{m.memory_type.value}] {m.content}")

            memory_text = "Relevant memories from previous interactions:\n" + "\n".join(
                memory_lines
            )

            memory_msg = Message(
                role=MessageRole.SYSTEM,
                content=memory_text,
            )

            # Insert after the first system message (if any)
            result = list(messages)
            insert_idx = 0
            for i, msg in enumerate(result):
                if msg.role == MessageRole.SYSTEM:
                    insert_idx = i + 1
                    break

            result.insert(insert_idx, memory_msg)

        # Truncate if over token budget
        return self._truncate(result, _max_tokens)

    def _truncate(
        self, messages: list[Message], max_tokens: int | None = None
    ) -> list[Message]:
        """Remove oldest non-system messages if over token budget."""
        budget = max_tokens if max_tokens is not None else self._max_context_tokens
        tokens = estimate_messages_tokens(messages)
        if tokens <= budget:
            return messages

        # Keep system messages and the last message (current query)
        # Remove from the middle (oldest non-system messages first)
        result = list(messages)
        truncated = False

        while estimate_messages_tokens(result) > budget and len(result) > 2:
            # Find the first non-system message that isn't the last
            for i in range(len(result) - 1):
                if result[i].role != MessageRole.SYSTEM:
                    result.pop(i)
                    truncated = True
                    break
            else:
                break  # Only system messages left

        if truncated:
            # Insert truncation marker after system messages
            marker_idx = 0
            for i, msg in enumerate(result):
                if msg.role == MessageRole.SYSTEM:
                    marker_idx = i + 1
                else:
                    break
            result.insert(
                marker_idx,
                Message(
                    role=MessageRole.SYSTEM,
                    content=(
                        "[Earlier conversation history truncated for context limits]"
                    ),
                ),
            )

        return result
