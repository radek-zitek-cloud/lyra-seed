"""Automatic fact extraction — LLM-based memory extraction after agent turns."""

import json
import logging

from agent_platform.llm.models import LLMConfig, Message, MessageRole
from agent_platform.memory.chroma_memory_store import ChromaMemoryStore
from agent_platform.memory.models import (
    DEFAULT_VISIBILITY,
    MemoryEntry,
    MemoryType,
    MemoryVisibility,
)
from agent_platform.observation.events import Event, EventType
from agent_platform.observation.in_process_event_bus import InProcessEventBus

logger = logging.getLogger(__name__)

DEFAULT_EXTRACTION_PROMPT = (
    "Extract useful facts, preferences, and decisions from the "
    "conversation. Return a JSON array: "
    '[{"content": "...", "memory_type": "fact", "importance": 0.5}]'
)


class FactExtractor:
    """Extracts facts/preferences/decisions from agent responses."""

    def __init__(
        self,
        llm_provider: object,
        extraction_model: str,
        memory_store: ChromaMemoryStore,
        event_bus: InProcessEventBus | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self._llm = llm_provider
        self._model = extraction_model
        self._store = memory_store
        self._event_bus = event_bus
        self._system_prompt = system_prompt or DEFAULT_EXTRACTION_PROMPT

    async def extract(
        self,
        agent_id: str,
        assistant_message: str,
        conversation_context: list[Message],
        memory_sharing: dict[str, str] | None = None,
        extraction_model: str | None = None,
    ) -> list[MemoryEntry]:
        """Extract memories from an assistant response.

        Args:
            extraction_model: Override the default model for this call.

        Returns list of created MemoryEntry objects.
        Failures are caught and logged — never breaks the caller.
        """
        try:
            return await self._do_extract(
                agent_id,
                assistant_message,
                conversation_context,
                memory_sharing,
                extraction_model,
            )
        except Exception:
            logger.exception("Fact extraction failed for agent %s", agent_id)
            return []

    async def _do_extract(
        self,
        agent_id: str,
        assistant_message: str,
        conversation_context: list[Message],
        memory_sharing: dict[str, str] | None,
        extraction_model: str | None = None,
    ) -> list[MemoryEntry]:
        # Build context — last few messages + the response
        recent = conversation_context[-6:]
        context_text = "\n".join(
            f"{m.role}: {m.content}"
            for m in recent
            if isinstance(m.content, str) and m.content.strip()
        )

        llm_messages = [
            Message(role=MessageRole.SYSTEM, content=self._system_prompt),
            Message(
                role=MessageRole.HUMAN,
                content=f"Conversation context:\n{context_text}\n\n"
                f"Latest assistant response:\n{assistant_message}",
            ),
        ]

        model = extraction_model or self._model
        config = LLMConfig(model=model, temperature=0.0)

        logger.info(
            "Extraction input for agent %s (model=%s):\n%s",
            agent_id,
            model,
            llm_messages[1].content[:500],
        )

        response = await self._llm.complete(llm_messages, config=config)

        logger.info(
            "Extraction output for agent %s: %s",
            agent_id,
            response.content[:200] if response.content else "(empty)",
        )

        if not response.content:
            return []

        # Parse JSON from response
        raw = response.content.strip()
        # Handle markdown code blocks
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            raw = raw.rsplit("```", 1)[0]
        items = json.loads(raw)

        if not isinstance(items, list):
            return []

        entries: list[MemoryEntry] = []
        for item in items:
            if not isinstance(item, dict) or "content" not in item:
                continue

            mem_type_str = item.get("memory_type", "fact")
            try:
                mem_type = MemoryType(mem_type_str)
            except ValueError:
                mem_type = MemoryType.FACT

            # Determine visibility
            visibility = self._resolve_visibility(mem_type, memory_sharing)

            entry = MemoryEntry(
                agent_id=agent_id,
                content=item["content"],
                memory_type=mem_type,
                importance=min(1.0, max(0.0, float(item.get("importance", 0.5)))),
                visibility=visibility,
            )

            await self._store.add(entry)
            entries.append(entry)

            if self._event_bus:
                await self._event_bus.emit(
                    Event(
                        agent_id=agent_id,
                        event_type=EventType.MEMORY_WRITE,
                        module="memory.extractor",
                        payload={
                            "source": "auto_extract",
                            "memory_id": entry.id,
                            "memory_type": mem_type.value,
                            "visibility": visibility.value,
                            "content_preview": entry.content[:100],
                        },
                    )
                )

        if entries:
            logger.info(
                "Extracted %d memories for agent %s",
                len(entries),
                agent_id,
            )
        return entries

    @staticmethod
    def _resolve_visibility(
        mem_type: MemoryType,
        memory_sharing: dict[str, str] | None,
    ) -> MemoryVisibility:
        """Determine visibility for an extracted memory."""
        if memory_sharing and mem_type.value in memory_sharing:
            try:
                return MemoryVisibility(memory_sharing[mem_type.value])
            except ValueError:
                pass
        return DEFAULT_VISIBILITY.get(mem_type, MemoryVisibility.PRIVATE)
