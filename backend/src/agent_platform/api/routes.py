"""API routes for agent management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_platform.core.models import Agent, AgentConfig, AgentStatus, HITLPolicy

router = APIRouter()


class CreateAgentRequest(BaseModel):
    name: str
    template: str | None = None  # config/prompt resolution name
    config: AgentConfig | None = None


class PromptRequest(BaseModel):
    message: str


class HITLRespondRequest(BaseModel):
    approved: bool
    message: str | None = None


def _resolve_config_from_files(template_name: str) -> AgentConfig:
    """Resolve a full AgentConfig from source files and platform defaults.

    Resolution order:
    1. {prompts_dir}/{template_name}.json for model, hitl, temperature, etc.
    2. {prompts_dir}/{template_name}.md for system prompt
    3. Falls back to default.json / default.md / platform defaults
    """
    from agent_platform.api._deps import (
        get_agent_config_resolver,
        get_default_model,
        get_platform_config,
        get_system_prompt_resolver,
    )

    resolve_prompt = get_system_prompt_resolver()
    resolve_config = get_agent_config_resolver()

    config = AgentConfig()
    file_config = resolve_config(template_name)

    # Apply file-based config overrides (name.json > default.json)
    if file_config.model:
        config.model = file_config.model
    else:
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

    if file_config.hitl is not None:
        config.hitl_timeout_seconds = file_config.hitl.timeout_seconds

    if file_config.memoryGC is not None:
        config.prune_threshold = file_config.memoryGC.prune_threshold
        config.prune_max_entries = file_config.memoryGC.max_entries

    if file_config.context is not None:
        config.max_context_tokens = file_config.context.max_tokens
        config.memory_top_k = file_config.context.memory_top_k

    if file_config.summary_model is not None:
        config.summary_model = file_config.summary_model
    if file_config.extraction_model is not None:
        config.extraction_model = file_config.extraction_model
    if file_config.orchestration_model is not None:
        config.orchestration_model = file_config.orchestration_model
    if file_config.max_subtasks is not None:
        config.max_subtasks = file_config.max_subtasks
    if file_config.auto_extract is not None:
        config.auto_extract = file_config.auto_extract
    if file_config.memory_sharing is not None:
        config.memory_sharing = file_config.memory_sharing
    if file_config.allowed_mcp_servers is not None:
        config.allowed_mcp_servers = file_config.allowed_mcp_servers
    if file_config.allowed_tools is not None:
        config.allowed_tools = file_config.allowed_tools

    # Apply platform defaults for fields not set by file config
    pc = get_platform_config()
    if pc:
        d = AgentConfig()
        if config.hitl_timeout_seconds == d.hitl_timeout_seconds:
            if file_config.hitl is None:
                config.hitl_timeout_seconds = pc.hitl.timeout_seconds
        if config.prune_threshold == d.prune_threshold:
            if file_config.memoryGC is None:
                config.prune_threshold = pc.memoryGC.prune_threshold
                config.prune_max_entries = pc.memoryGC.max_entries
        if config.max_context_tokens == d.max_context_tokens:
            if file_config.context is None:
                config.max_context_tokens = pc.context.max_tokens
                config.memory_top_k = pc.context.memory_top_k
        if config.summary_model is None:
            config.summary_model = pc.summaryModel
        if config.extraction_model is None:
            config.extraction_model = pc.extractionModel
        if config.orchestration_model is None:
            config.orchestration_model = pc.orchestrationModel
        if config.max_subtasks == AgentConfig().max_subtasks:
            if file_config.max_subtasks is None:
                config.max_subtasks = pc.maxSubtasks

    # Apply system prompt from template.md
    config.system_prompt = resolve_prompt(template_name)

    return config


@router.post("/agents", status_code=201)
async def create_agent(req: CreateAgentRequest):
    """Create a new agent with config resolved from files."""
    from agent_platform.api._deps import get_agent_repo

    repo = get_agent_repo()
    template_name = req.template or req.name
    config = _resolve_config_from_files(template_name)

    # Apply any explicit overrides from request
    if req.config:
        d = AgentConfig()
        if req.config.model != d.model:
            config.model = req.config.model
        if req.config.temperature != d.temperature:
            config.temperature = req.config.temperature
        if req.config.max_iterations != d.max_iterations:
            config.max_iterations = req.config.max_iterations
        if req.config.system_prompt != d.system_prompt:
            config.system_prompt = req.config.system_prompt
        if req.config.hitl_policy != d.hitl_policy:
            config.hitl_policy = req.config.hitl_policy
        if req.config.allowed_tools:
            config.allowed_tools = req.config.allowed_tools
        if req.config.allowed_mcp_servers is not None:
            config.allowed_mcp_servers = req.config.allowed_mcp_servers

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
    """Delete an agent and unregister any active loop."""
    from agent_platform.api._deps import get_agent_repo, get_loop_registry

    repo = get_agent_repo()

    # Unregister any active loop before deletion
    loop_registry = get_loop_registry()
    if loop_registry:
        loop_registry.unregister(agent_id)

    deleted = await repo.delete(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "ok"}


@router.get("/agents/{agent_id}/children")
async def list_children(agent_id: str):
    """List child agents of a given parent."""
    from agent_platform.api._deps import get_agent_repo

    repo = get_agent_repo()
    parent = await repo.get(agent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    children = await repo.list_children(agent_id)
    return [c.model_dump(mode="json") for c in children]


@router.post("/agents/{agent_id}/prompt")
async def prompt_agent(agent_id: str, req: PromptRequest):
    """Send a prompt to an agent."""
    from agent_platform.api._deps import get_agent_repo, get_runtime

    repo = get_agent_repo()
    agent = await repo.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status in (AgentStatus.COMPLETED, AgentStatus.FAILED):
        raise HTTPException(
            status_code=409,
            detail=f"Agent is {agent.status.value} and cannot accept prompts",
        )

    runtime = get_runtime()
    response = await runtime.run(agent_id, req.message)
    return response.model_dump(mode="json")


@router.post("/agents/{agent_id}/reset")
async def reset_agent(agent_id: str):
    """Reset a failed/completed agent back to idle."""
    from agent_platform.api._deps import get_agent_repo

    repo = get_agent_repo()
    agent = await repo.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status == AgentStatus.IDLE:
        return agent.model_dump(mode="json")
    agent.status = AgentStatus.IDLE
    await repo.update(agent.id, agent)
    return agent.model_dump(mode="json")


@router.post("/agents/{agent_id}/reload-config")
async def reload_agent_config(agent_id: str):
    """Reload agent config and system prompt from source files.

    Re-resolves the agent's config from its template/name .md and .json
    files, applies platform defaults, updates the agent record, and
    patches the conversation's system message so the agent sees the
    new prompt on its next turn.
    """
    from agent_platform.api._deps import (
        get_agent_repo,
        get_conversation_repo,
        get_loop_registry,
    )

    repo = get_agent_repo()
    conv_repo = get_conversation_repo()

    agent = await repo.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Unregister any active loop (conversation is being cleared)
    loop_registry = get_loop_registry()
    if loop_registry:
        loop_registry.unregister(agent_id)

    # Re-resolve config from source files using agent name
    new_config = _resolve_config_from_files(agent.name)

    # Track what changed
    old_prompt = agent.config.system_prompt
    old_model = agent.config.model

    # Update agent config
    agent.config = new_config
    await repo.update(agent.id, agent)

    # Clear conversation — delete existing and let runtime create
    # a fresh one with the new system prompt on next turn
    convos = await conv_repo.list(filters={"agent_id": agent_id})
    for conv in convos:
        await conv_repo.delete(conv.id)

    return {
        "status": "reloaded",
        "agent_id": agent_id,
        "prompt_changed": old_prompt != new_config.system_prompt,
        "model_changed": old_model != new_config.model,
        "conversation_cleared": len(convos) > 0,
    }


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
