"""Vector store protocol."""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class VectorResult(BaseModel):
    """A single result from a vector similarity search."""

    id: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class VectorStore(Protocol):
    """Abstract interface for vector storage and similarity search."""

    async def store(
        self,
        id: str,
        vector: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None: ...

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorResult]: ...

    async def delete(self, id: str) -> bool: ...
