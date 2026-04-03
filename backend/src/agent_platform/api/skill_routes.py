"""API routes for skill listing (read-only)."""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/skills")
async def list_skills():
    """List all loaded skills."""
    from agent_platform.api._deps import get_skill_provider

    provider = get_skill_provider()
    return [
        {
            "name": s.name,
            "description": s.description,
            "parameters": s.parameters,
        }
        for s in provider._skills.values()
    ]


@router.get("/skills/{skill_name}")
async def get_skill(skill_name: str):
    """Get a skill by name, including its template."""
    from agent_platform.api._deps import get_skill_provider

    provider = get_skill_provider()
    skill = provider._skills.get(skill_name)
    if skill is None:
        raise HTTPException(
            status_code=404,
            detail="Skill not found",
        )
    return {
        "name": skill.name,
        "description": skill.description,
        "parameters": skill.parameters,
        "template": skill.template,
    }
