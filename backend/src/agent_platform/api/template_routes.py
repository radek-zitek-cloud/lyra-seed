"""API routes for agent template listing (read-only)."""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/templates")
async def list_templates():
    """List all available agent templates."""
    from agent_platform.api._deps import get_template_provider

    provider = get_template_provider()
    return [
        {
            "name": t.name,
            "description": t.description,
            "has_prompt": t.has_prompt,
            "config_keys": list(t.config.keys()),
        }
        for t in provider.get_templates().values()
    ]


@router.get("/templates/{name}")
async def get_template(name: str):
    """Get an agent template by name."""
    from agent_platform.api._deps import get_template_provider

    provider = get_template_provider()
    tmpl = provider.get_template(name)
    if tmpl is None:
        raise HTTPException(
            status_code=404,
            detail="Template not found",
        )
    return {
        "name": tmpl.name,
        "description": tmpl.description,
        "config": tmpl.config,
        "has_prompt": tmpl.has_prompt,
    }
