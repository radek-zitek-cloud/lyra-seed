"""Message API routes — inter-agent messaging from the UI."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_platform.core.models import AgentMessage, MessageType

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
    from agent_platform.api._deps import get_event_bus, get_message_repo

    repo = get_message_repo()
    if repo is None:
        raise HTTPException(status_code=500, detail="Message repo not configured")

    msg = AgentMessage(
        from_agent_id=req.from_agent_id or "human",
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

    return _msg_to_dict(msg)


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
