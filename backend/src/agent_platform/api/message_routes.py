"""Message API routes — inter-agent messaging from the UI."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_platform.core.models import AgentMessage, AgentStatus, MessageType

logger = logging.getLogger(__name__)

router = APIRouter()


class SendMessageRequest(BaseModel):
    content: str
    message_type: str = "guidance"
    from_agent_id: str | None = None


@router.get("/agents/{agent_id}/messages")
async def get_agent_messages(
    agent_id: str,
    direction: str = "all",
):
    """List messages for an agent."""
    from agent_platform.api._deps import get_message_repo

    repo = get_message_repo()
    if repo is None:
        return []
    msgs = await repo.list_for_agent(agent_id, direction=direction)
    return [_msg_to_dict(m) for m in msgs]


@router.post("/agents/{agent_id}/messages", status_code=201)
async def send_message_to_agent(agent_id: str, req: SendMessageRequest):
    """Send a message to an agent (from human or another agent)."""
    from agent_platform.api._deps import (
        get_agent_repo,
        get_event_bus,
        get_message_repo,
    )

    repo = get_message_repo()
    if repo is None:
        raise HTTPException(status_code=500, detail="Message repo not configured")

    # Resolve sender: explicit > agent's parent > "human"
    from_id = req.from_agent_id
    if not from_id:
        agent_repo = get_agent_repo()
        agent = await agent_repo.get(agent_id)
        if agent and agent.parent_agent_id:
            from_id = agent.parent_agent_id
        else:
            from_id = "human"

    msg = AgentMessage(
        from_agent_id=from_id,
        to_agent_id=agent_id,
        content=req.content,
        message_type=MessageType(req.message_type),
    )
    await repo.create(msg)

    # Emit events
    event_bus = get_event_bus()
    from agent_platform.observation.events import Event, EventType

    await event_bus.emit(
        Event(
            agent_id=msg.from_agent_id,
            event_type=EventType.MESSAGE_SENT,
            module="api.messages",
            payload={
                "message_id": msg.id,
                "to_agent_id": agent_id,
                "message_type": msg.message_type.value,
            },
        )
    )
    await event_bus.emit(
        Event(
            agent_id=agent_id,
            event_type=EventType.MESSAGE_RECEIVED,
            module="api.messages",
            payload={
                "message_id": msg.id,
                "from_agent_id": msg.from_agent_id,
                "message_type": msg.message_type.value,
            },
        )
    )

    # Any message to an idle agent triggers a turn
    await _wake_idle_agent(agent_id, msg)

    return _msg_to_dict(msg)


async def _wake_idle_agent(agent_id: str, msg: AgentMessage) -> None:
    """If the target agent is idle, trigger a background runtime turn."""
    from agent_platform.api._deps import get_agent_repo, get_message_repo, get_runtime

    try:
        repo = get_agent_repo()
        agent = await repo.get(agent_id)
        if agent is None or agent.status != AgentStatus.IDLE:
            return

        runtime = get_runtime()
        prompt = f"[{msg.message_type.value} from {msg.from_agent_id}]: {msg.content}"
        # For actionable messages, instruct to respond back
        if msg.message_type.value in ("task", "question"):
            prompt += (
                f"\n\nWhen done, send the result back to "
                f"{msg.from_agent_id} using send_message with "
                f'message_type "result".'
            )

        # Consume the message (mark as delivered)
        msg_repo = get_message_repo()
        if msg_repo:
            await msg_repo.delete(msg.id)

        async def _run() -> None:
            try:
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
        logger.exception("Error in _wake_idle_agent for %s", agent_id)


def _msg_to_dict(m: AgentMessage) -> dict:
    return {
        "id": m.id,
        "from_agent_id": m.from_agent_id,
        "to_agent_id": m.to_agent_id,
        "content": m.content,
        "message_type": m.message_type.value,
        "timestamp": m.timestamp.isoformat(),
        "in_reply_to": m.in_reply_to,
    }
