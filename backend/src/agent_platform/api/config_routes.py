"""API routes for configuration file browsing and editing."""

import logging
import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])


def _get_project_root() -> Path:
    from agent_platform.api._deps import _project_root

    if _project_root is None:
        raise HTTPException(500, "Project root not configured")
    return Path(_project_root)


def _list_files(directory: Path, extension: str) -> list[dict]:
    """List files in a directory with metadata."""
    if not directory.exists():
        return []
    files = []
    for p in sorted(directory.glob(f"*{extension}")):
        if p.is_file():
            files.append(
                {
                    "name": p.name,
                    "path": str(p.relative_to(_get_project_root())),
                    "size": p.stat().st_size,
                }
            )
    # Include subdirectories
    for sub in sorted(directory.iterdir()):
        if sub.is_dir():
            for p in sorted(sub.glob(f"*{extension}")):
                if p.is_file():
                    files.append(
                        {
                            "name": f"{sub.name}/{p.name}",
                            "path": str(
                                p.relative_to(_get_project_root())
                            ),
                            "size": p.stat().st_size,
                        }
                    )
    return files


@router.get("/files")
async def list_config_files():
    """List all configuration files grouped by category."""
    root = _get_project_root()

    return {
        "platform": [
            {
                "name": "lyra.config.json",
                "path": "lyra.config.json",
                "size": (root / "lyra.config.json").stat().st_size
                if (root / "lyra.config.json").exists()
                else 0,
            },
            {
                "name": ".env",
                "path": ".env",
                "size": (root / ".env").stat().st_size
                if (root / ".env").exists()
                else 0,
            },
        ],
        "agent_configs": [
            f
            for f in _list_files(root / "prompts", ".json")
            if "/" not in f["name"]
        ],
        "agent_prompts": [
            f
            for f in _list_files(root / "prompts", ".md")
            if "/" not in f["name"]
            and f["name"] != "README.md"
        ],
        "system_prompts": [
            f
            for f in _list_files(
                root / "prompts" / "system", ".md"
            )
            if "/" not in f["name"]
        ],
        "skills": _list_files(root / "skills", ".md"),
    }


@router.get("/file")
async def read_config_file(path: str):
    """Read a configuration file's content."""
    root = _get_project_root()
    file_path = root / path

    # Security: ensure path stays within project root
    try:
        file_path.resolve().relative_to(root.resolve())
    except ValueError:
        raise HTTPException(403, "Path outside project root")

    if not file_path.exists():
        raise HTTPException(404, "File not found")

    return {
        "path": path,
        "content": file_path.read_text(encoding="utf-8"),
    }


class FileUpdate(BaseModel):
    path: str
    content: str


@router.put("/file")
async def write_config_file(req: FileUpdate):
    """Write/update a configuration file."""
    root = _get_project_root()
    file_path = root / req.path

    # Security: ensure path stays within project root
    try:
        file_path.resolve().relative_to(root.resolve())
    except ValueError:
        raise HTTPException(403, "Path outside project root")

    # Only allow editing known config directories
    allowed_prefixes = (
        "lyra.config.json",
        ".env",
        "prompts/",
        "skills/",
    )
    if not any(req.path.startswith(p) for p in allowed_prefixes):
        raise HTTPException(
            403, "Can only edit config, prompt, and skill files"
        )

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(req.content, encoding="utf-8")

    return {"status": "saved", "path": req.path}


@router.delete("/file")
async def delete_config_file(path: str):
    """Delete a configuration file."""
    root = _get_project_root()
    file_path = root / path

    # Security: ensure path stays within project root
    try:
        file_path.resolve().relative_to(root.resolve())
    except ValueError:
        raise HTTPException(403, "Path outside project root")

    # Only allow deleting agent configs, agent prompts, and skills
    deletable_prefixes = ("prompts/", "skills/")
    non_deletable = ("prompts/system/",)
    if not any(path.startswith(p) for p in deletable_prefixes):
        raise HTTPException(
            403, "Can only delete agent configs, prompts, and skills"
        )
    if any(path.startswith(p) for p in non_deletable):
        raise HTTPException(
            403, "Cannot delete system prompts"
        )

    if not file_path.exists():
        raise HTTPException(404, "File not found")

    file_path.unlink()
    return {"status": "deleted", "path": path}


@router.post("/reload")
async def reload_config():
    """Reload configuration, skills, and prompts without restarting."""
    from agent_platform.api._deps import (
        _project_root,
        get_skill_provider,
    )

    reloaded = []

    # Reload skills from disk
    try:
        provider = get_skill_provider()
        provider.reload()
        reloaded.append(
            f"skills ({len(provider._skills)} loaded)"
        )
    except Exception as e:
        logger.exception("Failed to reload skills")
        reloaded.append(f"skills (error: {e})")

    # Platform config reloads on every agent creation already
    reloaded.append("platform config (reloads per agent creation)")
    # Prompts reload on every agent creation already
    reloaded.append("agent prompts (reload per agent creation)")

    return {
        "status": "reloaded",
        "reloaded": reloaded,
        "note": "MCP server changes require a full restart.",
    }


@router.post("/restart")
async def restart_server():
    """Restart the backend server process.

    Works with uvicorn --reload by touching a source file
    to trigger the file watcher. Falls back to os._exit()
    if the touch doesn't apply.
    """
    import asyncio

    root = _get_project_root()

    # Touch a .py file to trigger uvicorn --reload watcher
    trigger = (
        root
        / "backend"
        / "src"
        / "agent_platform"
        / "__init__.py"
    )
    if trigger.exists():
        trigger.touch()
        logger.info(
            "Touched %s to trigger uvicorn reload", trigger
        )

    # Schedule hard exit as fallback after 2 seconds
    # (gives time for the response to be sent)
    async def _delayed_exit():
        await asyncio.sleep(2)
        logger.info("Forcing process exit for restart")
        os._exit(0)

    asyncio.create_task(_delayed_exit())

    return {
        "status": "restarting",
        "note": "Server will restart momentarily.",
    }
