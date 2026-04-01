"""Memory as tools — remember, recall, forget."""

import json
import time
from typing import Any

from agent_platform.memory.chroma_memory_store import ChromaMemoryStore
from agent_platform.memory.models import MemoryEntry, MemoryType
from agent_platform.observation.events import Event, EventType
from agent_platform.observation.in_process_event_bus import InProcessEventBus
from agent_platform.tools.models import Tool, ToolResult, ToolType


class MemoryToolProvider:
    """ToolProvider exposing remember, recall, forget operations."""

    def __init__(
        self,
        memory_store: ChromaMemoryStore,
        event_bus: InProcessEventBus | None = None,
    ) -> None:
        self._store = memory_store
        self._event_bus = event_bus

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="remember",
                description="Store a memory for future retrieval",
                input_schema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The content to remember",
                        },
                        "memory_type": {
                            "type": "string",
                            "enum": [t.value for t in MemoryType],
                            "description": "Type of memory",
                        },
                        "importance": {
                            "type": "number",
                            "description": "Importance 0.0-1.0",
                        },
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID",
                        },
                    },
                    "required": ["content", "agent_id"],
                },
                tool_type=ToolType.PROMPT_MACRO,
                source="memory",
            ),
            Tool(
                name="recall",
                description="Retrieve relevant memories by semantic search",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "agent_id": {
                            "type": "string",
                            "description": "Agent ID",
                        },
                        "memory_type": {
                            "type": "string",
                            "enum": [t.value for t in MemoryType],
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results",
                        },
                    },
                    "required": ["query", "agent_id"],
                },
                tool_type=ToolType.PROMPT_MACRO,
                source="memory",
            ),
            Tool(
                name="forget",
                description="Delete a specific memory by ID",
                input_schema={
                    "type": "object",
                    "properties": {
                        "memory_id": {
                            "type": "string",
                            "description": "Memory entry ID to delete",
                        },
                    },
                    "required": ["memory_id"],
                },
                tool_type=ToolType.PROMPT_MACRO,
                source="memory",
            ),
        ]

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        start = time.monotonic()
        if name == "remember":
            return await self._remember(arguments, start)
        elif name == "recall":
            return await self._recall(arguments, start)
        elif name == "forget":
            return await self._forget(arguments, start)
        return ToolResult(
            success=False, error=f"Unknown tool: {name}"
        )

    async def _remember(
        self, args: dict[str, Any], start: float
    ) -> ToolResult:
        memory_type = MemoryType(
            args.get("memory_type", "fact")
        )
        entry = MemoryEntry(
            agent_id=args["agent_id"],
            content=args["content"],
            memory_type=memory_type,
            importance=args.get("importance", 0.5),
        )
        await self._store.add(entry)

        if self._event_bus:
            await self._event_bus.emit(
                Event(
                    agent_id=args["agent_id"],
                    event_type=EventType.MEMORY_WRITE,
                    module="memory.tools",
                    payload={
                        "memory_id": entry.id,
                        "memory_type": memory_type.value,
                        "content_preview": entry.content[:100],
                    },
                )
            )

        duration = int((time.monotonic() - start) * 1000)
        return ToolResult(
            success=True,
            output=entry.id,
            duration_ms=duration,
        )

    async def _recall(
        self, args: dict[str, Any], start: float
    ) -> ToolResult:
        memory_type = None
        if "memory_type" in args and args["memory_type"]:
            memory_type = MemoryType(args["memory_type"])

        results = await self._store.search(
            query=args["query"],
            agent_id=args.get("agent_id"),
            memory_type=memory_type,
            top_k=args.get("top_k", 5),
        )

        if self._event_bus and args.get("agent_id"):
            await self._event_bus.emit(
                Event(
                    agent_id=args["agent_id"],
                    event_type=EventType.MEMORY_READ,
                    module="memory.tools",
                    payload={
                        "query": args["query"],
                        "results_count": len(results),
                    },
                )
            )

        # Update access timestamps
        for r in results:
            await self._store.update_access(r.id)

        duration = int((time.monotonic() - start) * 1000)
        memories_output = [
            {
                "id": r.id,
                "content": r.content,
                "type": r.memory_type.value,
                "importance": r.importance,
            }
            for r in results
        ]
        return ToolResult(
            success=True,
            output=json.dumps(memories_output),
            duration_ms=duration,
        )

    async def _forget(
        self, args: dict[str, Any], start: float
    ) -> ToolResult:
        deleted = await self._store.delete(args["memory_id"])
        duration = int((time.monotonic() - start) * 1000)
        if deleted:
            return ToolResult(
                success=True,
                output=f"Memory {args['memory_id']} deleted",
                duration_ms=duration,
            )
        return ToolResult(
            success=False,
            error=f"Memory {args['memory_id']} not found",
            duration_ms=duration,
        )
