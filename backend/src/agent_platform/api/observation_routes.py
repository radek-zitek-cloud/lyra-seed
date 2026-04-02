"""Observation API routes — events, conversations, tools."""

from fastapi import APIRouter, Query

from agent_platform.observation.events import EventFilter, EventType

router = APIRouter()


@router.get("/agents")
async def list_agents():
    """List all agents."""
    from agent_platform.api._deps import get_agent_repo

    repo = get_agent_repo()
    agents = await repo.list()
    return [a.model_dump(mode="json") for a in agents]


@router.get("/agents/{agent_id}/events")
async def get_agent_events(
    agent_id: str,
    event_type: str | None = Query(None),
    module: str | None = Query(None),
):
    """Query events for a specific agent."""
    from agent_platform.api._deps import get_event_bus

    event_bus = get_event_bus()
    filters = EventFilter(agent_id=agent_id)
    if event_type:
        filters.event_types = [EventType(event_type)]
    if module:
        filters.module = module

    events = await event_bus.query(filters)
    return [e.model_dump(mode="json") for e in events]


@router.get("/agents/{agent_id}/conversations")
async def get_agent_conversations(agent_id: str):
    """Get conversation history for an agent."""
    from agent_platform.api._deps import get_conversation_repo

    repo = get_conversation_repo()
    conversations = await repo.list(filters={"agent_id": agent_id})
    return [c.model_dump(mode="json") for c in conversations]


@router.get("/tools")
async def list_tools():
    """List all registered tools."""
    from agent_platform.api._deps import get_tool_registry

    registry = get_tool_registry()
    tools = await registry.list_tools()
    return [t.model_dump(mode="json") for t in tools]


@router.get("/tools/{tool_name}/calls")
async def get_tool_calls(tool_name: str):
    """Get call history for a specific tool."""
    from agent_platform.api._deps import get_event_bus

    event_bus = get_event_bus()
    # Query both TOOL_CALL and TOOL_RESULT events
    call_events = await event_bus.query(
        EventFilter(event_types=[EventType.TOOL_CALL, EventType.TOOL_RESULT])
    )
    # Filter by tool_name in payload
    filtered = [e for e in call_events if e.payload.get("tool_name") == tool_name]
    return [e.model_dump(mode="json") for e in filtered]


@router.get("/agents/{agent_id}/cost")
async def get_agent_cost(agent_id: str):
    """Get cost summary for a specific agent."""
    from agent_platform.api._deps import get_event_bus
    from agent_platform.observation.cost_tracker import compute_agent_cost

    event_bus = get_event_bus()
    return await compute_agent_cost(event_bus, agent_id)


@router.get("/cost")
async def get_total_cost():
    """Get total cost summary across all agents."""
    from agent_platform.api._deps import get_event_bus
    from agent_platform.observation.cost_tracker import compute_total_cost

    event_bus = get_event_bus()
    return await compute_total_cost(event_bus)
