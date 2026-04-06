"""Agent loop — scheduled periodic wake-ups for long-running agents.

Provides the `agent_loop` tool that lets agents set up, adjust, and stop
periodic wake-up calls. A background scheduler checks the registry every
second and sends TASK messages to due agents, triggering auto-wake.
"""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from agent_platform.tools.models import Tool, ToolResult, ToolType

logger = logging.getLogger(__name__)

MIN_INTERVAL_SECONDS = 10


class LoopEntry(BaseModel):
    """A registered periodic wake-up."""

    agent_id: str
    interval: float  # seconds
    message: str
    next_wake: datetime


class LoopRegistry:
    """In-memory registry of scheduled agent wake-ups."""

    def __init__(self) -> None:
        self._loops: dict[str, LoopEntry] = {}

    def register(
        self, agent_id: str, interval: float, message: str
    ) -> LoopEntry:
        interval = max(interval, MIN_INTERVAL_SECONDS)
        entry = LoopEntry(
            agent_id=agent_id,
            interval=interval,
            message=message,
            next_wake=datetime.now(UTC),
        )
        self._loops[agent_id] = entry
        logger.info(
            "Loop registered: agent=%s interval=%ss", agent_id, interval
        )
        return entry

    def unregister(self, agent_id: str) -> bool:
        removed = self._loops.pop(agent_id, None)
        if removed:
            logger.info("Loop unregistered: agent=%s", agent_id)
        return removed is not None

    def get(self, agent_id: str) -> LoopEntry | None:
        return self._loops.get(agent_id)

    def get_due(self) -> list[LoopEntry]:
        now = datetime.now(UTC)
        return [e for e in self._loops.values() if e.next_wake <= now]

    def advance(self, agent_id: str) -> None:
        entry = self._loops.get(agent_id)
        if entry:
            now = datetime.now(UTC)
            # Skip missed intervals — schedule from now
            from datetime import timedelta

            entry.next_wake = now + timedelta(seconds=entry.interval)

    def all_entries(self) -> list[LoopEntry]:
        return list(self._loops.values())

    def clear(self) -> None:
        self._loops.clear()


class AgentLoopProvider:
    """ToolProvider exposing the agent_loop tool."""

    def __init__(self, registry: LoopRegistry) -> None:
        self._registry = registry

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="agent_loop",
                description=(
                    "Set up, adjust, or stop periodic wake-up calls. "
                    "Use action 'start' to begin receiving scheduled "
                    "TASK messages at the given interval (seconds). "
                    "Use 'stop' to cancel. Use 'status' to check. "
                    f"Minimum interval: {MIN_INTERVAL_SECONDS}s."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["start", "stop", "status"],
                            "description": "Action to perform.",
                        },
                        "interval": {
                            "type": "number",
                            "description": (
                                "Wake-up interval in seconds "
                                f"(min {MIN_INTERVAL_SECONDS}). "
                                "Required for 'start'."
                            ),
                        },
                        "message": {
                            "type": "string",
                            "description": (
                                "Message content for each wake-up. "
                                "Defaults to 'Scheduled wake-up'."
                            ),
                        },
                    },
                    "required": ["action"],
                },
                tool_type=ToolType.INTERNAL,
                source="agent_loop",
            ),
        ]

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        start = time.monotonic()
        if name != "agent_loop":
            return ToolResult(success=False, error=f"Unknown tool: {name}")

        action = arguments.get("action", "status")
        agent_id = arguments.get("agent_id", "")

        if action == "start":
            interval = arguments.get("interval")
            if interval is None:
                return ToolResult(
                    success=False,
                    error="'interval' is required for action 'start'",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
            message = arguments.get("message", "Scheduled wake-up")
            entry = self._registry.register(agent_id, interval, message)
            return ToolResult(
                success=True,
                output=json.dumps({
                    "status": "started",
                    "agent_id": agent_id,
                    "interval": entry.interval,
                    "message": entry.message,
                }),
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        elif action == "stop":
            removed = self._registry.unregister(agent_id)
            return ToolResult(
                success=True,
                output=json.dumps({
                    "status": "stopped" if removed else "not_found",
                    "agent_id": agent_id,
                }),
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        elif action == "status":
            entry = self._registry.get(agent_id)
            if entry:
                return ToolResult(
                    success=True,
                    output=json.dumps({
                        "active": True,
                        "agent_id": agent_id,
                        "interval": entry.interval,
                        "message": entry.message,
                        "next_wake": entry.next_wake.isoformat(),
                    }),
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
            return ToolResult(
                success=True,
                output=json.dumps({
                    "active": False,
                    "agent_id": agent_id,
                }),
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        return ToolResult(
            success=False,
            error=f"Unknown action: {action}",
            duration_ms=int((time.monotonic() - start) * 1000),
        )


async def loop_scheduler(
    registry: LoopRegistry,
    wake_fn: Any,
) -> None:
    """Background task — checks registry every second, wakes due agents.

    wake_fn(agent_id: str, message: str) -> None
    """
    logger.info("Loop scheduler started")
    try:
        while True:
            await asyncio.sleep(1)
            due = registry.get_due()
            for entry in due:
                try:
                    await wake_fn(entry.agent_id, entry.message)
                except Exception:
                    logger.exception(
                        "Loop scheduler: failed to wake %s",
                        entry.agent_id,
                    )
                registry.advance(entry.agent_id)
    except asyncio.CancelledError:
        logger.info("Loop scheduler stopped")
