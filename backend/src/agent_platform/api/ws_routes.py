"""WebSocket routes for real-time event streaming."""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/agents/{agent_id}/events/stream")
async def agent_event_stream(websocket: WebSocket, agent_id: str):
    """Stream real-time events for a specific agent."""
    from agent_platform.api._deps import get_event_bus

    await websocket.accept()
    event_bus = get_event_bus()

    try:
        async for event in event_bus.subscribe(agent_id=agent_id):
            try:
                await websocket.send_json(event.model_dump(mode="json"))
            except (WebSocketDisconnect, RuntimeError):
                break
    except WebSocketDisconnect:
        pass
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await asyncio.wait_for(websocket.close(), timeout=2.0)
            except Exception:
                pass


@router.websocket("/events/stream")
async def global_event_stream(websocket: WebSocket):
    """Stream all real-time events (global)."""
    from agent_platform.api._deps import get_event_bus

    await websocket.accept()
    event_bus = get_event_bus()

    try:
        async for event in event_bus.subscribe():
            try:
                await websocket.send_json(event.model_dump(mode="json"))
            except (WebSocketDisconnect, RuntimeError):
                break
    except WebSocketDisconnect:
        pass
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await asyncio.wait_for(websocket.close(), timeout=2.0)
            except Exception:
                pass
