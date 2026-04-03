"""API routes for configuration file browsing and editing."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
        "agents": _list_files(root / "prompts", ".json")
        + _list_files(root / "prompts", ".md"),
        "system_prompts": _list_files(
            root / "prompts" / "system", ".md"
        ),
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
