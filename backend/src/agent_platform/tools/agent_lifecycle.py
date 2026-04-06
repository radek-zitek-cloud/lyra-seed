"""Agent lifecycle operations — spawn, wait, stop, dismiss, check, list, get result."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from agent_platform.core.models import (
    Agent,
    AgentConfig,
    AgentResponse,
    AgentStatus,
)
from agent_platform.llm.models import MessageRole
from agent_platform.observation.events import Event, EventType
from agent_platform.tools.models import ToolResult

if TYPE_CHECKING:
    from agent_platform.tools.agent_spawner import AgentSpawnerProvider

logger = logging.getLogger(__name__)


async def spawn_agent(
    provider: AgentSpawnerProvider, args: dict[str, Any], start: float
) -> ToolResult:
    """Create a child agent and run it async in a background task."""
    parent_id = args.get("agent_id")
    child_name = args["name"]
    task_text = args["task"]

    # Depth guard
    depth = await get_spawn_depth(provider, parent_id)
    if depth >= provider._max_spawn_depth:
        return ToolResult(
            success=False,
            error=f"Max spawn depth ({provider._max_spawn_depth}) reached.",
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    # Resolve child config
    child_config = await resolve_child_config(provider, args)

    # Create child
    child = Agent(
        name=child_name,
        config=child_config,
        parent_agent_id=parent_id,
    )
    await provider._agent_repo.create(child)

    # Emit AGENT_SPAWN
    if parent_id:
        await provider._event_bus.emit(
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
    provider._completion_events[child.id] = completion_event

    bg_task = asyncio.create_task(
        _run_child_background(provider, child, task_text, parent_id)
    )
    provider._running_tasks[child.id] = bg_task

    duration = int((time.monotonic() - start) * 1000)
    return ToolResult(
        success=True,
        output=json.dumps({"child_agent_id": child.id, "status": "running"}),
        duration_ms=duration,
    )


async def _run_child_background(
    provider: AgentSpawnerProvider,
    child: Agent,
    task: str,
    parent_id: str | None,
) -> None:
    """Background task that runs a child agent to completion."""
    start = time.monotonic()
    try:
        response = await run_child(provider, child, task)
        duration = int((time.monotonic() - start) * 1000)
        await provider._event_bus.emit(
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
        await provider._agent_repo.update(child.id, child)
    except Exception as e:
        logger.exception("Child agent %s failed", child.id)
        duration = int((time.monotonic() - start) * 1000)
        await provider._event_bus.emit(
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
        await provider._agent_repo.update(child.id, child)
    finally:
        provider._running_tasks.pop(child.id, None)
        evt = provider._completion_events.pop(child.id, None)
        if evt:
            evt.set()


async def run_child(
    provider: AgentSpawnerProvider, child: Agent, task: str
) -> AgentResponse:
    """Run a child agent using the full AgentRuntime loop."""
    from agent_platform.core.runtime import AgentRuntime
    from agent_platform.tools.registry import ToolRegistry

    runtime = AgentRuntime(
        agent_repo=provider._agent_repo,
        conversation_repo=provider._conv_repo,
        llm_provider=provider._llm,
        event_bus=provider._event_bus,
        tool_registry=provider._tool_registry or ToolRegistry(),
        context_manager=provider._context_manager,
        extractor=provider._extractor,
        message_repo=provider._message_repo,
    )
    return await runtime.run(child.id, task)


async def wait_for_agent(
    provider: AgentSpawnerProvider, args: dict[str, Any], start: float
) -> ToolResult:
    """Wait for a child agent to finish."""
    child_id = args["child_agent_id"]
    timeout = args.get("timeout", 300)

    evt = provider._completion_events.get(child_id)
    if evt and not evt.is_set():
        try:
            await asyncio.wait_for(evt.wait(), timeout=timeout)
        except TimeoutError:
            return ToolResult(
                success=False,
                error=f"Timeout waiting for agent {child_id}",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

    return await get_agent_result(provider, args, start)


async def check_agent_status(
    provider: AgentSpawnerProvider, args: dict[str, Any], start: float
) -> ToolResult:
    """Non-blocking status check."""
    child_id = args["child_agent_id"]
    child = await provider._agent_repo.get(child_id)
    if child is None:
        return ToolResult(
            success=False,
            error=f"Agent {child_id} not found",
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    content_preview = None
    convos = await provider._conv_repo.list(filters={"agent_id": child_id})
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


async def stop_agent(
    provider: AgentSpawnerProvider, args: dict[str, Any], start: float
) -> ToolResult:
    """Cancel a running child's background task."""
    child_id = args["child_agent_id"]
    task = provider._running_tasks.get(child_id)

    if task and not task.done():
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
        except (asyncio.CancelledError, TimeoutError):
            pass

    child = await provider._agent_repo.get(child_id)
    if child and child.status == AgentStatus.RUNNING:
        child.status = AgentStatus.IDLE
        await provider._agent_repo.update(child.id, child)

    return ToolResult(
        success=True,
        output=f"Agent {child_id} stopped",
        duration_ms=int((time.monotonic() - start) * 1000),
    )


async def dismiss_agent(
    provider: AgentSpawnerProvider, args: dict[str, Any], start: float
) -> ToolResult:
    """Mark a child as COMPLETED (no longer reusable)."""
    child_id = args["child_agent_id"]
    child = await provider._agent_repo.get(child_id)
    if child is None:
        return ToolResult(
            success=False,
            error=f"Agent {child_id} not found",
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    child.status = AgentStatus.COMPLETED
    await provider._agent_repo.update(child.id, child)
    return ToolResult(
        success=True,
        output=f"Agent {child_id} dismissed",
        duration_ms=int((time.monotonic() - start) * 1000),
    )


async def get_agent_result(
    provider: AgentSpawnerProvider, args: dict[str, Any], start: float
) -> ToolResult:
    """Get child's current status and last response."""
    child_id = args["child_agent_id"]
    child = await provider._agent_repo.get(child_id)
    if child is None:
        return ToolResult(
            success=False,
            error=f"Agent {child_id} not found",
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    content = None
    convos = await provider._conv_repo.list(filters={"agent_id": child_id})
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


async def list_child_agents(
    provider: AgentSpawnerProvider, args: dict[str, Any], start: float
) -> ToolResult:
    """List all child agents."""
    parent_id = args.get("agent_id")
    if not parent_id:
        return ToolResult(
            success=False,
            error="agent_id required",
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    children = await provider._agent_repo.list_children(parent_id)
    return ToolResult(
        success=True,
        output=json.dumps(
            [
                {
                    "id": c.id,
                    "name": c.name,
                    "status": c.status.value,
                }
                for c in children
            ]
        ),
        duration_ms=int((time.monotonic() - start) * 1000),
    )


# ── Helpers ────────────────────────────────────────


async def get_spawn_depth(provider: AgentSpawnerProvider, agent_id: str | None) -> int:
    """Count how many parent levels exist above this agent."""
    depth = 0
    current_id = agent_id
    while current_id:
        agent = await provider._agent_repo.get(current_id)
        if agent is None or agent.parent_agent_id is None:
            break
        depth += 1
        current_id = agent.parent_agent_id
    return depth


async def resolve_child_config(
    provider: AgentSpawnerProvider, args: dict[str, Any]
) -> AgentConfig:
    """Resolve child config from template, parent, and overrides."""
    parent_id = args.get("agent_id")
    parent = await provider._agent_repo.get(parent_id) if parent_id else None
    child_config = AgentConfig()
    template = args.get("template")

    if template and provider._resolve_prompt:
        child_config.system_prompt = provider._resolve_prompt(template)
        if provider._resolve_config:
            fc = provider._resolve_config(template)
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
            if fc.allowed_mcp_servers is not None:
                child_config.allowed_mcp_servers = fc.allowed_mcp_servers
            if fc.allowed_tools is not None:
                child_config.allowed_tools = fc.allowed_tools
        if parent:
            if child_config.model == AgentConfig().model:
                child_config.model = parent.config.model
            if child_config.temperature == AgentConfig().temperature:
                child_config.temperature = parent.config.temperature
            if child_config.allowed_mcp_servers is None:
                child_config.allowed_mcp_servers = parent.config.allowed_mcp_servers
            if not child_config.allowed_tools:
                child_config.allowed_tools = parent.config.allowed_tools
    elif parent:
        child_config.model = parent.config.model
        child_config.temperature = parent.config.temperature
        child_config.allowed_mcp_servers = parent.config.allowed_mcp_servers
        child_config.allowed_tools = parent.config.allowed_tools

    # Resolve system prompt from default.md if not set by template or override
    if (
        child_config.system_prompt == AgentConfig().system_prompt
        and provider._resolve_prompt
    ):
        child_config.system_prompt = provider._resolve_prompt("default")

    # Explicit overrides
    if args.get("system_prompt"):
        child_config.system_prompt = args["system_prompt"]
    if args.get("model"):
        child_config.model = args["model"]
    if args.get("temperature") is not None:
        child_config.temperature = args["temperature"]

    return child_config
