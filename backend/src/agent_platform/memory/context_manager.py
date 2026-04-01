"""Context manager — assembles messages with memory injection."""

from agent_platform.llm.models import Message, MessageRole
from agent_platform.memory.chroma_memory_store import ChromaMemoryStore


class ContextManager:
    """Retrieves relevant memories and injects them into the conversation."""

    def __init__(
        self,
        memory_store: ChromaMemoryStore,
        top_k: int = 5,
    ) -> None:
        self._store = memory_store
        self._top_k = top_k

    async def assemble(
        self,
        agent_id: str,
        messages: list[Message],
        query: str,
    ) -> list[Message]:
        """Assemble messages with relevant memories injected.

        Returns a new list with a memory system message prepended
        if relevant memories are found.
        """
        memories = await self._store.search(
            query=query,
            agent_id=agent_id,
            top_k=self._top_k,
        )

        if not memories:
            return list(messages)

        # Update access timestamps
        for m in memories:
            await self._store.update_access(m.id)

        # Build memory injection message
        memory_lines = []
        for m in memories:
            memory_lines.append(
                f"- [{m.memory_type.value}] {m.content}"
            )

        memory_text = (
            "Relevant memories from previous interactions:\n"
            + "\n".join(memory_lines)
        )

        memory_msg = Message(
            role=MessageRole.SYSTEM,
            content=memory_text,
        )

        # Insert after the first system message (if any),
        # or at the beginning
        result = list(messages)
        insert_idx = 0
        for i, msg in enumerate(result):
            if msg.role == MessageRole.SYSTEM:
                insert_idx = i + 1
                break

        result.insert(insert_idx, memory_msg)
        return result
