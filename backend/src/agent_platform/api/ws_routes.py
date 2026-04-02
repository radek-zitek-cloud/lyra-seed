"""SSE routes for real-time event streaming.

Uses Server-Sent Events instead of WebSockets for cleaner shutdown
behavior — SSE connections are regular HTTP responses that complete
when the generator returns, not persistent background tasks.
"""

import asyncio
import logging

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

router = APIRouter()
logger = logging.getLogger(__name__)


async def _event_generator(
    request: Request,
    agent_id: str | None = None,
):
    """Yield SSE-formatted events until client disconnects or bus closes."""
    from agent_platform.api._deps import get_event_bus

    event_bus = get_event_bus()

    if event_bus.is_closed:
        return

    sub = event_bus.subscribe(agent_id=agent_id)

    try:
        async for event in sub:
            # Check if client disconnected
            if await request.is_disconnected():
                break
            data = event.model_dump_json()
            yield f"data: {data}\n\n"
    except asyncio.CancelledError:
        pass


@router.get("/agents/{agent_id}/events/stream")
async def agent_event_stream(request: Request, agent_id: str):
    """Stream real-time events for a specific agent via SSE."""
    return StreamingResponse(
        _event_generator(request, agent_id=agent_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/events/stream")
async def global_event_stream(request: Request):
    """Stream all real-time events via SSE."""
    return StreamingResponse(
        _event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
