"""API routes for prompt macro management."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent_platform.tools.prompt_macro import PromptMacro

router = APIRouter()


class MacroRequest(BaseModel):
    name: str
    description: str = ""
    template: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    output_instructions: str = ""


@router.post("/macros", status_code=201)
async def create_macro(req: MacroRequest):
    """Create a new prompt macro."""
    from agent_platform.api._deps import get_macro_repo, get_macro_provider

    macro = PromptMacro(
        name=req.name,
        description=req.description,
        template=req.template,
        parameters=req.parameters,
        output_instructions=req.output_instructions,
    )
    repo = get_macro_repo()
    await repo.create(macro)

    # Register in provider
    provider = get_macro_provider()
    provider.add_macro(macro)

    return macro.model_dump(mode="json")


@router.get("/macros")
async def list_macros():
    """List all prompt macros."""
    from agent_platform.api._deps import get_macro_repo

    repo = get_macro_repo()
    macros = await repo.list()
    return [m.model_dump(mode="json") for m in macros]


@router.get("/macros/{macro_id}")
async def get_macro(macro_id: str):
    """Get a prompt macro by ID."""
    from agent_platform.api._deps import get_macro_repo

    repo = get_macro_repo()
    macro = await repo.get(macro_id)
    if macro is None:
        raise HTTPException(status_code=404, detail="Macro not found")
    return macro.model_dump(mode="json")


@router.put("/macros/{macro_id}")
async def update_macro(macro_id: str, req: MacroRequest):
    """Update a prompt macro."""
    from agent_platform.api._deps import get_macro_repo, get_macro_provider

    repo = get_macro_repo()
    existing = await repo.get(macro_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Macro not found")

    existing.name = req.name
    existing.description = req.description
    existing.template = req.template
    existing.parameters = req.parameters
    existing.output_instructions = req.output_instructions

    await repo.update(macro_id, existing)

    # Update in provider
    provider = get_macro_provider()
    provider.add_macro(existing)

    return existing.model_dump(mode="json")


@router.delete("/macros/{macro_id}")
async def delete_macro(macro_id: str):
    """Delete a prompt macro."""
    from agent_platform.api._deps import get_macro_repo, get_macro_provider

    repo = get_macro_repo()
    existing = await repo.get(macro_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Macro not found")

    await repo.delete(macro_id)

    # Remove from provider
    provider = get_macro_provider()
    provider.remove_macro(existing.name)

    return {"status": "deleted"}
