"""Agent messaging — send, receive, and auto-wake."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from agent_platform.core.models import (
    AgentMessage,
    AgentStatus,
    MessageType,
)
from agent_platform.observation.events import Event, EventType
from agent_platform.tools.models import ToolResult

if TYPE_CHECKING:
    from agent_platform.tools.agent_spawner import AgentSpawnerProvider

logger = logging.getLogger(__name__)

ACTIONABLE_MSG_TYPES = {"task", "question", "guidance", "result", "answer"}


def build_wake_prompt(msg: AgentMessage) -> str:
    """Build the prompt injected when auto-waking an idle agent."""
    prompt = (
        f"[{msg.message_type.value} from {msg.from_agent_id}]:"
        f" {msg.content}"
    )
    if msg.message_type.value in ("task", "question"):
        prompt += (
            f"\n\nWhen done, send the result back to "
            f"{msg.from_agent_id} using send_message with "
            f'message_type "result".'
        )
    return prompt


async def send_message(
    provider: AgentSpawnerProvider, args: dict[str, Any], start: float
) -> ToolResult:
    """Send a message to another agent."""
    if not provider._message_repo:
        return ToolResult(
            success=False,
            error="Message repo not configured",
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    from_id = args.get("agent_id", "human")
    to_id = args["target_agent_id"]
    content = args["content"]
    msg_type = MessageType(args["message_type"])

    # Reject messages to terminated agents
    target = await provider._agent_repo.get(to_id)
    if target and target.status in (
        AgentStatus.COMPLETED,
        AgentStatus.FAILED,
    ):
        return ToolResult(
            success=False,
            error=(
                f"Agent {to_id} is {target.status.value} "
                f"and cannot receive messages"
            ),
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    msg = AgentMessage(
        from_agent_id=from_id,
        to_agent_id=to_id,
        content=content,
        message_type=msg_type,
        in_reply_to=args.get("in_reply_to"),
    )
    await provider._message_repo.create(msg)

    # Emit events
    await provider._event_bus.emit(
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
    await provider._event_bus.emit(
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

    # Auto-wake idle target on actionable messages
    await wake_idle_agent(provider, to_id, msg)

    return ToolResult(
        success=True,
        output=json.dumps(
            {"message_id": msg.id, "status": "sent"}
        ),
        duration_ms=int((time.monotonic() - start) * 1000),
    )


async def wake_idle_agent(
    provider: AgentSpawnerProvider,
    agent_id: str,
    msg: AgentMessage,
) -> None:
    """If idle and message is actionable, trigger a runtime turn."""
    try:
        agent = await provider._agent_repo.get(agent_id)
        if agent is None or agent.status != AgentStatus.IDLE:
            return

        if msg.message_type.value not in ACTIONABLE_MSG_TYPES:
            return

        prompt = build_wake_prompt(msg)

        # Consume the message
        if provider._message_repo:
            await provider._message_repo.delete(msg.id)

        async def _run() -> None:
            try:
                from agent_platform.core.runtime import AgentRuntime
                from agent_platform.tools.registry import ToolRegistry

                runtime = AgentRuntime(
                    agent_repo=provider._agent_repo,
                    conversation_repo=provider._conv_repo,
                    llm_provider=provider._llm,
                    event_bus=provider._event_bus,
                    tool_registry=(
                        provider._tool_registry or ToolRegistry()
                    ),
                    context_manager=provider._context_manager,
                    extractor=provider._extractor,
                    message_repo=provider._message_repo,
                )
                await runtime.run(agent_id, prompt)
            except Exception:
                logger.exception(
                    "Failed to wake agent %s on message", agent_id
                )

        asyncio.create_task(_run())
        logger.info(
            "Auto-woke idle agent %s on %s message",
            agent_id,
            msg.message_type.value,
        )
    except Exception:
        pass  # Never break the sender's flow


async def receive_messages(
    provider: AgentSpawnerProvider, args: dict[str, Any], start: float
) -> ToolResult:
    """Check inbox for messages."""
    if not provider._message_repo:
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

    msgs = await provider._message_repo.list_for_agent(
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
