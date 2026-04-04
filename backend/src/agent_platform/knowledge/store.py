"""Knowledge store — ChromaDB-backed document chunk storage."""

import logging
from pathlib import Path
from typing import Any

import chromadb

from agent_platform.knowledge.chunker import DocumentChunk, chunk_markdown

logger = logging.getLogger(__name__)

COLLECTION_NAME = "knowledge_base"


class KnowledgeStore:
    """Stores and searches document chunks using ChromaDB."""

    def __init__(
        self,
        persist_dir: str | None = None,
        embedding_fn: Any = None,
    ) -> None:
        if persist_dir:
            self._client = chromadb.PersistentClient(path=persist_dir)
        else:
            self._client = chromadb.Client()

        kwargs: dict[str, Any] = {
            "name": COLLECTION_NAME,
            "metadata": {"hnsw:space": "cosine"},
        }
        if embedding_fn is not None:
            kwargs["embedding_function"] = embedding_fn

        self._collection = self._client.get_or_create_collection(**kwargs)
        self._sources: set[str] = set()
        self._load_sources()

    def _load_sources(self) -> None:
        """Load known source files from existing collection."""
        try:
            result = self._collection.get(include=["metadatas"])
            if result and result["metadatas"]:
                for meta in result["metadatas"]:
                    if meta and "source" in meta:
                        self._sources.add(meta["source"])
        except Exception:
            pass

    def ingest(self, path: Path) -> int:
        """Ingest a markdown file — chunks, embeds, stores.

        Re-ingesting replaces existing chunks from the same source.
        Returns the number of chunks stored.
        """
        chunks = chunk_markdown(path)
        if not chunks:
            return 0

        source = path.name

        # Remove existing chunks from this source
        self._remove_source(source)

        # Add new chunks
        ids = [f"{source}:{i}" for i in range(len(chunks))]
        documents = [c.content for c in chunks]
        metadatas = [
            {"source": c.source, "heading_path": c.heading_path} for c in chunks
        ]

        self._collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        self._sources.add(source)

        logger.info("Ingested %s: %d chunks", source, len(chunks))
        return len(chunks)

    def _remove_source(self, source: str) -> None:
        """Remove all chunks from a specific source."""
        try:
            self._collection.delete(where={"source": source})
        except Exception:
            # ChromaDB may throw if no matching docs
            pass

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[DocumentChunk]:
        """Search for relevant chunks."""
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(top_k, max(self._collection.count(), 1)),
            )
        except Exception:
            logger.exception("Knowledge search failed")
            return []

        chunks: list[DocumentChunk] = []
        if results and results["documents"]:
            for doc, meta in zip(
                results["documents"][0],
                results["metadatas"][0],
            ):
                chunks.append(
                    DocumentChunk(
                        content=doc,
                        source=meta.get("source", ""),
                        heading_path=meta.get("heading_path", ""),
                    )
                )

        return chunks

    def ingest_directory(self, dir_path: Path) -> int:
        """Ingest all .md files from a directory."""
        if not dir_path.exists():
            return 0

        total = 0
        for path in sorted(dir_path.glob("*.md")):
            if path.name.startswith("README"):
                continue
            total += self.ingest(path)

        return total

    def get_sources(self) -> list[str]:
        """Return list of ingested document names."""
        return sorted(self._sources)
