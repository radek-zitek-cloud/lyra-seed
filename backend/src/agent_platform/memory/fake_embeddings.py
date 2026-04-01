"""Fake embedding provider for testing — deterministic vectors from text hash."""

import hashlib
import math
import struct


class FakeEmbeddingProvider:
    """Generates deterministic embeddings from text hashes. No API calls."""

    def __init__(self, dimensions: int = 64) -> None:
        self._dimensions = dimensions

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        return self._hash_to_vector(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        return [self._hash_to_vector(t) for t in texts]

    def _hash_to_vector(self, text: str) -> list[float]:
        """Convert text to a deterministic unit vector via SHA-256."""
        # Generate enough hash bytes for the dimensions
        h = hashlib.sha256(text.encode()).digest()
        # Extend hash if needed
        while len(h) < self._dimensions * 4:
            h += hashlib.sha256(h).digest()
        # Convert to floats
        floats = list(
            struct.unpack(f"<{self._dimensions}f", h[: self._dimensions * 4])
        )
        # Normalize to unit vector
        magnitude = math.sqrt(sum(x * x for x in floats))
        if magnitude > 0:
            floats = [x / magnitude for x in floats]
        return floats

    # --- ChromaDB EmbeddingFunction interface ---

    def __call__(self, input: list[str]) -> list[list[float]]:
        """ChromaDB legacy EmbeddingFunction interface."""
        return self.embed_batch(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        """ChromaDB 1.x: embed documents for storage."""
        return self.embed_batch(input)

    def embed_query(self, input: list[str]) -> list[list[float]]:
        """ChromaDB 1.x: embed queries for search."""
        return self.embed_batch(input)

    @staticmethod
    def name() -> str:
        """ChromaDB EmbeddingFunction name (required by ChromaDB 1.x)."""
        return "fake_embedding_provider"
