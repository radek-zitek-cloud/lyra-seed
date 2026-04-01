"""API routes for agent management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_platform.core.models import Agent, AgentConfig

router = APIRouter()


class CreateAgentRequest(BaseModel):
    name: str
    config: AgentConfig | None = None


class PromptRequest(BaseModel):
    message: str


class HITLRespondRequest(BaseModel):
    approved: bool
    message: str | None = None


@router.post("/agents", status_code=201)
async def create_agent(req: CreateAgentRequest):
    """Create a new agent with system prompt resolved from config."""
    from agent_platform.api._deps import get_agent_repo, get_system_prompt_resolver

    repo = get_agent_repo()
    resolve_prompt = get_system_prompt_resolver()

    config = req.config or AgentConfig()

    # If system_prompt is the default, resolve from file
    if config.system_prompt == AgentConfig().system_prompt:
        config.system_prompt = resolve_prompt(req.name)

    agent = Agent(name=req.name, config=config)
    await repo.create(agent)
    return agent.model_dump(mode="json")


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details."""
    from agent_platform.api._deps import get_agent_repo

    repo = get_agent_repo()
    agent = await repo.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.model_dump(mode="json")


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """Delete an agent."""
    from agent_platform.api._deps import get_agent_repo

    repo = get_agent_repo()
    deleted = await repo.delete(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "ok"}


@router.post("/agents/{agent_id}/prompt")
async def prompt_agent(agent_id: str, req: PromptRequest):
    """Send a prompt to an agent."""
    from agent_platform.api._deps import get_agent_repo, get_runtime

    repo = get_agent_repo()
    agent = await repo.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    runtime = get_runtime()
    response = await runtime.run(agent_id, req.message)
    return response.model_dump(mode="json")


@router.post("/agents/{agent_id}/hitl-respond")
async def hitl_respond(agent_id: str, req: HITLRespondRequest):
    """Respond to a pending HITL gate."""
    from agent_platform.api._deps import get_runtime

    runtime = get_runtime()
    success = await runtime.hitl_respond(
        agent_id, approved=req.approved, message=req.message
    )
    if not success:
        raise HTTPException(
            status_code=404,
            detail="No pending HITL gate for this agent",
        )
    return {"status": "ok"}
