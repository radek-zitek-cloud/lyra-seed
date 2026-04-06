"""Memory API routes — browse, search, manage memories."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from agent_platform.memory.models import MemoryType, MemoryVisibility

router = APIRouter()


class MemoryPatch(BaseModel):
    importance: float | None = None
    archived: bool | None = None


@router.get("/memories")
async def list_memories(
    agent_id: str | None = Query(None),
    memory_type: str | None = Query(None),
    q: str | None = Query(None),
    archived: bool | None = Query(None),
    visibility: str | None = Query(None),
    limit: int = Query(50, le=200),
):
    """List or search memories with optional filters."""
    from agent_platform.api._deps import get_memory_store

    store = get_memory_store()

    # Semantic search mode
    if q:
        mt = MemoryType(memory_type) if memory_type else None
        results = await store.search(
            query=q,
            agent_id=agent_id,
            memory_type=mt,
            top_k=limit,
            include_public=True,
        )
        return [_entry_to_dict(e) for e in results]

    # List mode with filters
    mt = MemoryType(memory_type) if memory_type else None
    vis = MemoryVisibility(visibility) if visibility else None
    results = await store.list_all(
        agent_id=agent_id,
        memory_type=mt,
        archived=archived,
        visibility=vis,
        limit=limit,
    )
    return [_entry_to_dict(e) for e in results]


@router.get("/memories/{memory_id}")
async def get_memory(memory_id: str):
    """Get a single memory by ID."""
    from agent_platform.api._deps import get_memory_store

    store = get_memory_store()
    entry = await store.get(memory_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _entry_to_dict(entry)


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a memory."""
    from agent_platform.api._deps import get_memory_store

    store = get_memory_store()
    deleted = await store.delete(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "ok"}


@router.patch("/memories/{memory_id}")
async def update_memory(memory_id: str, patch: MemoryPatch):
    """Update a memory's importance or archived status."""
    from agent_platform.api._deps import get_memory_store

    store = get_memory_store()
    entry = await store.get(memory_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory not found")

    if patch.importance is not None:
        entry.importance = max(0.0, min(1.0, patch.importance))
    if patch.archived is not None:
        entry.archived = patch.archived

    await store.update_entry(entry)
    return _entry_to_dict(entry)


def _entry_to_dict(entry) -> dict:
    """Convert MemoryEntry to API response dict."""
    return {
        "id": entry.id,
        "agent_id": entry.agent_id,
        "content": entry.content,
        "memory_type": entry.memory_type.value,
        "importance": entry.importance,
        "visibility": entry.visibility.value,
        "created_at": entry.created_at.isoformat(),
        "last_accessed_at": entry.last_accessed_at.isoformat(),
        "access_count": entry.access_count,
        "decay_score": round(entry.decay_score, 4),
        "archived": entry.archived,
    }
