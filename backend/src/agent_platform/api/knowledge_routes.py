"""Knowledge base API routes — sources and chunks."""

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/knowledge/sources")
async def list_sources():
    """List all ingested knowledge sources with chunk counts."""
    from agent_platform.api._deps import get_knowledge_store

    store = get_knowledge_store()
    sources = store.get_sources()
    result = []
    for source in sources:
        chunks = store.get_chunks(source=source)
        result.append({"source": source, "chunk_count": len(chunks)})
    return result


@router.get("/knowledge/chunks")
async def list_chunks(source: str | None = Query(None)):
    """List knowledge chunks, optionally filtered by source."""
    from agent_platform.api._deps import get_knowledge_store

    store = get_knowledge_store()
    chunks = store.get_chunks(source=source)
    return [
        {
            "source": c.source,
            "heading_path": c.heading_path,
            "content": c.content,
            "directory": c.directory,
        }
        for c in chunks
    ]


@router.get("/knowledge/search")
async def search_knowledge(
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=50),
):
    """Semantic search across knowledge base."""
    from agent_platform.api._deps import get_knowledge_store

    store = get_knowledge_store()
    chunks = store.search(query=q, top_k=top_k)
    return [
        {
            "source": c.source,
            "heading_path": c.heading_path,
            "content": c.content,
            "directory": c.directory,
        }
        for c in chunks
    ]
