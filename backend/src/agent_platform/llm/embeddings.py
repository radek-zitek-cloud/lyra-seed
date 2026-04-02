"""Embedding provider protocol."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Abstract interface for embedding providers."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_single(self, text: str) -> list[float]: ...

    def embed_query(self, input: list[str]) -> list[list[float]]:
        """ChromaDB 1.x sync interface for query embedding."""
        ...
