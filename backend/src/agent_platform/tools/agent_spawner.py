"""Agent spawner — tools for creating, managing, and messaging sub-agents."""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from agent_platform.core.models import (
    Agent,
    AgentConfig,
    AgentMessage,
    AgentResponse,
    AgentStatus,
    MessageType,
)
from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.db.sqlite_message_repo import SqliteMessageRepo
from agent_platform.llm.models import MessageRole
from agent_platform.observation.events import Event, EventType
from agent_platform.observation.in_process_event_bus import InProcessEventBus
from agent_platform.tools.models import Tool, ToolResult, ToolType

logger = logging.getLogger(__name__)


class AgentSpawnerProvider:
    """ToolProvider for spawning sub-agents, lifecycle management, and messaging."""

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
        # Async spawn tracking
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._completion_events: dict[str, asyncio.Event] = {}

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="spawn_agent",
                description=(
                    "Spawn an async sub-agent. Returns immediately with "
                    "child_agent_id. Use wait_for_agent to get results."
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
                tool_type=ToolType.PROMPT_MACRO,
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
                tool_type=ToolType.PROMPT_MACRO,
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
                tool_type=ToolType.PROMPT_MACRO,
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
                tool_type=ToolType.PROMPT_MACRO,
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
                tool_type=ToolType.PROMPT_MACRO,
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
                tool_type=ToolType.PROMPT_MACRO,
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
                    "required": ["target_agent_id", "content", "message_type"],
                },
                tool_type=ToolType.PROMPT_MACRO,
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
                tool_type=ToolType.PROMPT_MACRO,
                source="agent_spawner",
            ),
            Tool(
                name="dismiss_agent",
                description="Mark a child agent as COMPLETED (no longer reusable).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "child_agent_id": {"type": "string"},
                        "agent_id": {"type": "string"},
                    },
                    "required": ["child_agent_id"],
                },
                tool_type=ToolType.PROMPT_MACRO,
                source="agent_spawner",
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        start = time.monotonic()
        handlers = {
            "spawn_agent": self._spawn_agent,
            "wait_for_agent": self._wait_for_agent,
            "check_agent_status": self._check_agent_status,
            "stop_agent": self._stop_agent,
            "get_agent_result": self._get_agent_result,
            "list_child_agents": self._list_child_agents,
            "send_message": self._send_message,
            "receive_messages": self._receive_messages,
            "dismiss_agent": self._dismiss_agent,
        }
        handler = handlers.get(name)
        if handler is None:
            return ToolResult(success=False, error=f"Unknown tool: {name}")
        return await handler(arguments, start)

    async def cancel_all_tasks(self) -> None:
        """Cancel all running child tasks. Called on shutdown."""
        for child_id, task in list(self._running_tasks.items()):
            if not task.done():
                task.cancel()
                logger.info("Cancelled background task for agent %s", child_id)
        self._running_tasks.clear()
        self._completion_events.clear()

    # ── Spawn ──────────────────────────────────────────

    async def _spawn_agent(self, args: dict[str, Any], start: float) -> ToolResult:
        """Create a child agent and run it async in a background task."""
        parent_id = args.get("agent_id")
        child_name = args["name"]
        task_text = args["task"]

        # Depth guard
        depth = await self._get_spawn_depth(parent_id)
        if depth >= self._max_spawn_depth:
            return ToolResult(
                success=False,
                error=f"Max spawn depth ({self._max_spawn_depth}) reached.",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        # Resolve child config
        child_config = await self._resolve_child_config(args)

        # Create child
        child = Agent(
            name=child_name,
            config=child_config,
            parent_agent_id=parent_id,
        )
        await self._agent_repo.create(child)

        # Emit AGENT_SPAWN
        if parent_id:
            await self._event_bus.emit(
                Event(
                    agent_id=parent_id,
                    event_type=EventType.AGENT_SPAWN,
                    module="tools.agent_spawner",
                    payload={
                        "child_agent_id": child.id,
                        "child_name": child_name,
                        "task": task_text[:200],
                    },
                )
            )

        # Launch background task
        completion_event = asyncio.Event()
        self._completion_events[child.id] = completion_event

        bg_task = asyncio.create_task(
            self._run_child_background(child, task_text, parent_id)
        )
        self._running_tasks[child.id] = bg_task

        duration = int((time.monotonic() - start) * 1000)
        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "child_agent_id": child.id,
                    "status": "running",
                }
            ),
            duration_ms=duration,
        )

    async def _run_child_background(
        self, child: Agent, task: str, parent_id: str | None
    ) -> None:
        """Background task that runs a child agent to completion."""
        start = time.monotonic()
        try:
            response = await self._run_child(child, task)
            duration = int((time.monotonic() - start) * 1000)
            await self._event_bus.emit(
                Event(
                    agent_id=child.id,
                    event_type=EventType.AGENT_COMPLETE,
                    module="tools.agent_spawner",
                    payload={
                        "parent_agent_id": parent_id,
                        "content_preview": (
                            response.content[:200] if response.content else None
                        ),
                    },
                    duration_ms=duration,
                )
            )
        except asyncio.CancelledError:
            logger.info("Child agent %s cancelled", child.id)
            child.status = AgentStatus.IDLE
            await self._agent_repo.update(child.id, child)
        except Exception as e:
            logger.exception("Child agent %s failed", child.id)
            duration = int((time.monotonic() - start) * 1000)
            await self._event_bus.emit(
                Event(
                    agent_id=child.id,
                    event_type=EventType.ERROR,
                    module="tools.agent_spawner",
                    payload={
                        "parent_agent_id": parent_id,
                        "error": str(e)[:200],
                    },
                    duration_ms=duration,
                )
            )
            child.status = AgentStatus.FAILED
            await self._agent_repo.update(child.id, child)
        finally:
            self._running_tasks.pop(child.id, None)
            evt = self._completion_events.pop(child.id, None)
            if evt:
                evt.set()

    async def _run_child(self, child: Agent, task: str) -> AgentResponse:
        """Run a child agent using the full AgentRuntime loop."""
        from agent_platform.core.runtime import AgentRuntime
        from agent_platform.tools.registry import ToolRegistry

        runtime = AgentRuntime(
            agent_repo=self._agent_repo,
            conversation_repo=self._conv_repo,
            llm_provider=self._llm,
            event_bus=self._event_bus,
            tool_registry=self._tool_registry or ToolRegistry(),
            context_manager=self._context_manager,
            extractor=self._extractor,
            message_repo=self._message_repo,
        )
        return await runtime.run(child.id, task)

    # ── Lifecycle ──────────────────────────────────────

    async def _wait_for_agent(self, args: dict[str, Any], start: float) -> ToolResult:
        """Wait for a child agent to finish."""
        child_id = args["child_agent_id"]
        timeout = args.get("timeout", 300)

        evt = self._completion_events.get(child_id)
        if evt and not evt.is_set():
            try:
                await asyncio.wait_for(evt.wait(), timeout=timeout)
            except TimeoutError:
                return ToolResult(
                    success=False,
                    error=f"Timeout waiting for agent {child_id}",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )

        return await self._get_agent_result(args, start)

    async def _check_agent_status(
        self, args: dict[str, Any], start: float
    ) -> ToolResult:
        """Non-blocking status check."""
        child_id = args["child_agent_id"]
        child = await self._agent_repo.get(child_id)
        if child is None:
            return ToolResult(
                success=False,
                error=f"Agent {child_id} not found",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        # Get last message preview
        content_preview = None
        convos = await self._conv_repo.list(filters={"agent_id": child_id})
        if convos:
            for msg in reversed(convos[0].messages):
                if msg.role == MessageRole.ASSISTANT:
                    content_preview = str(msg.content)[:100] if msg.content else None
                    break

        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "child_agent_id": child.id,
                    "name": child.name,
                    "status": child.status.value,
                    "content_preview": content_preview,
                }
            ),
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    async def _stop_agent(self, args: dict[str, Any], start: float) -> ToolResult:
        """Cancel a running child's background task."""
        child_id = args["child_agent_id"]
        task = self._running_tasks.get(child_id)

        if task and not task.done():
            task.cancel()
            # Wait briefly for cancellation
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
            except (asyncio.CancelledError, TimeoutError):
                pass

        child = await self._agent_repo.get(child_id)
        if child and child.status == AgentStatus.RUNNING:
            child.status = AgentStatus.IDLE
            await self._agent_repo.update(child.id, child)

        return ToolResult(
            success=True,
            output=f"Agent {child_id} stopped",
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    async def _dismiss_agent(self, args: dict[str, Any], start: float) -> ToolResult:
        """Mark a child as COMPLETED (no longer reusable)."""
        child_id = args["child_agent_id"]
        child = await self._agent_repo.get(child_id)
        if child is None:
            return ToolResult(
                success=False,
                error=f"Agent {child_id} not found",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        child.status = AgentStatus.COMPLETED
        await self._agent_repo.update(child.id, child)
        return ToolResult(
            success=True,
            output=f"Agent {child_id} dismissed",
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    async def _get_agent_result(self, args: dict[str, Any], start: float) -> ToolResult:
        """Get child's current status and last response."""
        child_id = args["child_agent_id"]
        child = await self._agent_repo.get(child_id)
        if child is None:
            return ToolResult(
                success=False,
                error=f"Agent {child_id} not found",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        content = None
        convos = await self._conv_repo.list(filters={"agent_id": child_id})
        if convos:
            for msg in reversed(convos[0].messages):
                if msg.role == MessageRole.ASSISTANT:
                    content = msg.content
                    break

        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "child_agent_id": child.id,
                    "status": child.status.value,
                    "content": content,
                }
            ),
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    async def _list_child_agents(
        self, args: dict[str, Any], start: float
    ) -> ToolResult:
        parent_id = args.get("agent_id")
        if not parent_id:
            return ToolResult(
                success=False,
                error="agent_id required",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        children = await self._agent_repo.list_children(parent_id)
        return ToolResult(
            success=True,
            output=json.dumps(
                [
                    {"id": c.id, "name": c.name, "status": c.status.value}
                    for c in children
                ]
            ),
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    # ── Messaging ──────────────────────────────────────

    async def _send_message(self, args: dict[str, Any], start: float) -> ToolResult:
        """Send a message to another agent."""
        if not self._message_repo:
            return ToolResult(
                success=False,
                error="Message repo not configured",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        from_id = args.get("agent_id", "human")
        to_id = args["target_agent_id"]
        content = args["content"]
        msg_type = MessageType(args["message_type"])

        msg = AgentMessage(
            from_agent_id=from_id,
            to_agent_id=to_id,
            content=content,
            message_type=msg_type,
            in_reply_to=args.get("in_reply_to"),
        )
        await self._message_repo.create(msg)

        # Emit events
        await self._event_bus.emit(
            Event(
                agent_id=from_id,
                event_type=EventType.MESSAGE_SENT,
                module="tools.agent_spawner",
                payload={
                    "message_id": msg.id,
                    "to_agent_id": to_id,
                    "message_type": msg_type.value,
                    "content_preview": content[:100],
                },
            )
        )
        await self._event_bus.emit(
            Event(
                agent_id=to_id,
                event_type=EventType.MESSAGE_RECEIVED,
                module="tools.agent_spawner",
                payload={
                    "message_id": msg.id,
                    "from_agent_id": from_id,
                    "message_type": msg_type.value,
                    "content_preview": content[:100],
                },
            )
        )

        # Auto-wake idle target agent on actionable messages
        # Any message to an idle agent triggers a turn
        await self._wake_idle_agent(to_id, msg)

        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "message_id": msg.id,
                    "status": "sent",
                }
            ),
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    async def _wake_idle_agent(self, agent_id: str, msg: AgentMessage) -> None:
        """If agent is idle, trigger a background runtime turn."""
        try:
            agent = await self._agent_repo.get(agent_id)
            if agent is None or agent.status != AgentStatus.IDLE:
                return

            prompt = (
                f"[{msg.message_type.value} from {msg.from_agent_id}]: {msg.content}"
            )
            if msg.message_type.value in ("task", "question"):
                prompt += (
                    f"\n\nWhen done, send the result back to "
                    f"{msg.from_agent_id} using send_message with "
                    f'message_type "result".'
                )

            # Consume the message
            if self._message_repo:
                await self._message_repo.delete(msg.id)

            async def _run() -> None:
                try:
                    from agent_platform.core.runtime import AgentRuntime
                    from agent_platform.tools.registry import ToolRegistry

                    runtime = AgentRuntime(
                        agent_repo=self._agent_repo,
                        conversation_repo=self._conv_repo,
                        llm_provider=self._llm,
                        event_bus=self._event_bus,
                        tool_registry=self._tool_registry or ToolRegistry(),
                        context_manager=self._context_manager,
                        extractor=self._extractor,
                        message_repo=self._message_repo,
                    )
                    await runtime.run(agent_id, prompt)
                except Exception:
                    logger.exception("Failed to wake agent %s on message", agent_id)

            asyncio.create_task(_run())
            logger.info(
                "Auto-woke idle agent %s on %s message",
                agent_id,
                msg.message_type.value,
            )
        except Exception:
            pass  # Never break the sender's flow

    async def _receive_messages(self, args: dict[str, Any], start: float) -> ToolResult:
        """Check inbox for messages."""
        if not self._message_repo:
            return ToolResult(
                success=True,
                output="[]",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        agent_id = args.get("agent_id")
        if not agent_id:
            return ToolResult(
                success=False,
                error="agent_id required",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        msg_type = None
        if args.get("message_type"):
            msg_type = MessageType(args["message_type"])

        msgs = await self._message_repo.list_for_agent(
            agent_id,
            direction="inbox",
            message_type=msg_type,
            since=args.get("since"),
        )

        return ToolResult(
            success=True,
            output=json.dumps(
                [
                    {
                        "id": m.id,
                        "from_agent_id": m.from_agent_id,
                        "content": m.content,
                        "message_type": m.message_type.value,
                        "timestamp": m.timestamp.isoformat(),
                        "in_reply_to": m.in_reply_to,
                    }
                    for m in msgs
                ]
            ),
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    # ── Helpers ────────────────────────────────────────

    async def _get_spawn_depth(self, agent_id: str | None) -> int:
        depth = 0
        current_id = agent_id
        while current_id:
            agent = await self._agent_repo.get(current_id)
            if agent is None or agent.parent_agent_id is None:
                break
            depth += 1
            current_id = agent.parent_agent_id
        return depth

    async def _resolve_child_config(self, args: dict[str, Any]) -> AgentConfig:
        """Resolve child config from template, parent, and explicit overrides."""
        parent_id = args.get("agent_id")
        parent = await self._agent_repo.get(parent_id) if parent_id else None
        child_config = AgentConfig()
        template = args.get("template")

        if template and self._resolve_prompt:
            child_config.system_prompt = self._resolve_prompt(template)
            if self._resolve_config:
                fc = self._resolve_config(template)
                if fc.model:
                    child_config.model = fc.model
                if fc.temperature is not None:
                    child_config.temperature = fc.temperature
                if fc.max_iterations is not None:
                    child_config.max_iterations = fc.max_iterations
                if fc.hitl_policy is not None:
                    from agent_platform.core.models import HITLPolicy

                    child_config.hitl_policy = HITLPolicy(fc.hitl_policy)
                if fc.auto_extract is not None:
                    child_config.auto_extract = fc.auto_extract
            if parent:
                if child_config.model == AgentConfig().model:
                    child_config.model = parent.config.model
                if child_config.temperature == AgentConfig().temperature:
                    child_config.temperature = parent.config.temperature
        elif parent:
            child_config.model = parent.config.model
            child_config.temperature = parent.config.temperature

        # Explicit overrides
        if args.get("system_prompt"):
            child_config.system_prompt = args["system_prompt"]
        if args.get("model"):
            child_config.model = args["model"]
        if args.get("temperature") is not None:
            child_config.temperature = args["temperature"]

        return child_config
