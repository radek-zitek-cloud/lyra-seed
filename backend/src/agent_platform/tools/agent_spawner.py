"""Agent spawner — coordinator for lifecycle and messaging tools."""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from agent_platform.core.models import MessageType
from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.db.sqlite_message_repo import SqliteMessageRepo
from agent_platform.observation.in_process_event_bus import InProcessEventBus
from agent_platform.tools.agent_lifecycle import (
    check_agent_status,
    dismiss_agent,
    get_agent_result,
    list_child_agents,
    spawn_agent,
    stop_agent,
    wait_for_agent,
)
from agent_platform.tools.agent_messaging import (
    receive_messages,
    send_message,
)
from agent_platform.tools.models import Tool, ToolResult, ToolType

logger = logging.getLogger(__name__)


class AgentSpawnerProvider:
    """ToolProvider for spawning sub-agents, lifecycle, and messaging."""

    def __init__(
        self,
        agent_repo: SqliteAgentRepo,
        conversation_repo: SqliteConversationRepo,
        llm_provider: object,
        event_bus: InProcessEventBus,
        context_manager: object | None = None,
        extractor: object | None = None,
        system_prompt_resolver: Callable[[str], str] | None = None,
        agent_config_resolver: Callable | None = None,
        tool_registry: object | None = None,
        message_repo: SqliteMessageRepo | None = None,
        max_spawn_depth: int = 3,
    ) -> None:
        self._agent_repo = agent_repo
        self._conv_repo = conversation_repo
        self._llm = llm_provider
        self._event_bus = event_bus
        self._context_manager = context_manager
        self._extractor = extractor
        self._resolve_prompt = system_prompt_resolver
        self._resolve_config = agent_config_resolver
        self._tool_registry = tool_registry
        self._message_repo = message_repo
        self._max_spawn_depth = max_spawn_depth
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._completion_events: dict[str, asyncio.Event] = {}

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="spawn_agent",
                description=(
                    "Spawn an async sub-agent. Returns immediately with child_agent_id."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "task": {"type": "string"},
                        "template": {"type": "string"},
                        "system_prompt": {"type": "string"},
                        "model": {"type": "string"},
                        "temperature": {"type": "number"},
                        "agent_id": {"type": "string"},
                    },
                    "required": ["name", "task"],
                },
                tool_type=ToolType.INTERNAL,
                source="agent_spawner",
            ),
            Tool(
                name="wait_for_agent",
                description="Wait for a child agent to complete.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "child_agent_id": {"type": "string"},
                        "timeout": {"type": "number"},
                        "agent_id": {"type": "string"},
                    },
                    "required": ["child_agent_id"],
                },
                tool_type=ToolType.INTERNAL,
                source="agent_spawner",
            ),
            Tool(
                name="check_agent_status",
                description="Check a child agent's status (non-blocking).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "child_agent_id": {"type": "string"},
                        "agent_id": {"type": "string"},
                    },
                    "required": ["child_agent_id"],
                },
                tool_type=ToolType.INTERNAL,
                source="agent_spawner",
            ),
            Tool(
                name="stop_agent",
                description="Stop a running child agent.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "child_agent_id": {"type": "string"},
                        "agent_id": {"type": "string"},
                    },
                    "required": ["child_agent_id"],
                },
                tool_type=ToolType.INTERNAL,
                source="agent_spawner",
            ),
            Tool(
                name="get_agent_result",
                description="Get child agent's last response.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "child_agent_id": {"type": "string"},
                        "agent_id": {"type": "string"},
                    },
                    "required": ["child_agent_id"],
                },
                tool_type=ToolType.INTERNAL,
                source="agent_spawner",
            ),
            Tool(
                name="list_child_agents",
                description="List all child agents.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string"},
                    },
                    "required": [],
                },
                tool_type=ToolType.INTERNAL,
                source="agent_spawner",
            ),
            Tool(
                name="send_message",
                description="Send a message to another agent.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "target_agent_id": {"type": "string"},
                        "content": {"type": "string"},
                        "message_type": {
                            "type": "string",
                            "enum": [t.value for t in MessageType],
                        },
                        "in_reply_to": {"type": "string"},
                        "agent_id": {"type": "string"},
                    },
                    "required": [
                        "target_agent_id",
                        "content",
                        "message_type",
                    ],
                },
                tool_type=ToolType.INTERNAL,
                source="agent_spawner",
            ),
            Tool(
                name="receive_messages",
                description="Check inbox for messages (non-blocking).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "message_type": {"type": "string"},
                        "since": {"type": "string"},
                        "agent_id": {"type": "string"},
                    },
                    "required": [],
                },
                tool_type=ToolType.INTERNAL,
                source="agent_spawner",
            ),
            Tool(
                name="dismiss_agent",
                description=("Mark a child agent as COMPLETED (no longer reusable)."),
                input_schema={
                    "type": "object",
                    "properties": {
                        "child_agent_id": {"type": "string"},
                        "agent_id": {"type": "string"},
                    },
                    "required": ["child_agent_id"],
                },
                tool_type=ToolType.INTERNAL,
                source="agent_spawner",
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        start = time.monotonic()
        handlers = {
            "spawn_agent": spawn_agent,
            "wait_for_agent": wait_for_agent,
            "check_agent_status": check_agent_status,
            "stop_agent": stop_agent,
            "get_agent_result": get_agent_result,
            "list_child_agents": list_child_agents,
            "send_message": send_message,
            "receive_messages": receive_messages,
            "dismiss_agent": dismiss_agent,
        }
        handler = handlers.get(name)
        if handler is None:
            return ToolResult(success=False, error=f"Unknown tool: {name}")
        return await handler(self, arguments, start)

    async def cancel_all_tasks(self) -> None:
        """Cancel all running child tasks. Called on shutdown."""
        for child_id, task in list(self._running_tasks.items()):
            if not task.done():
                task.cancel()
                logger.info("Cancelled background task for agent %s", child_id)
        self._running_tasks.clear()
        self._completion_events.clear()
