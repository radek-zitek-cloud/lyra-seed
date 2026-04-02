"""API routes for agent management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_platform.core.models import Agent, AgentConfig, HITLPolicy

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
    """Create a new agent with config resolved from files.

    Resolution:
    1. {prompts_dir}/{name}.json for model, hitl_policy, temperature, etc.
    2. {prompts_dir}/{name}.md for system prompt
    3. Falls back to default.json / default.md / platform defaults
    """
    from agent_platform.api._deps import (
        get_agent_config_resolver,
        get_agent_repo,
        get_default_model,
        get_system_prompt_resolver,
    )

    repo = get_agent_repo()
    resolve_prompt = get_system_prompt_resolver()
    resolve_config = get_agent_config_resolver()

    config = req.config or AgentConfig()
    file_config = resolve_config(req.name)

    # Apply file-based config overrides (name.json > default.json)
    if file_config.model:
        config.model = file_config.model
    elif config.model == AgentConfig().model:
        config.model = get_default_model()

    if file_config.hitl_policy:
        config.hitl_policy = HITLPolicy(file_config.hitl_policy)

    if file_config.temperature is not None:
        config.temperature = file_config.temperature

    if file_config.max_iterations is not None:
        config.max_iterations = file_config.max_iterations

    if file_config.retry is not None:
        from agent_platform.core.models import AgentRetryConfig

        config.retry = AgentRetryConfig(
            max_retries=file_config.retry.max_retries,
            base_delay=file_config.retry.base_delay,
            max_delay=file_config.retry.max_delay,
            timeout=file_config.retry.timeout,
        )

    # Apply system prompt from name.md
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
