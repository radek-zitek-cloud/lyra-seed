"""Knowledge store — ChromaDB-backed document chunk storage."""

import hashlib
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
        self._source_hashes: dict[str, str] = {}
        self._load_sources()

    def _load_sources(self) -> None:
        """Load known source files and content hashes."""
        try:
            result = self._collection.get(include=["metadatas"])
            if result and result["metadatas"]:
                for meta in result["metadatas"]:
                    if meta and "source" in meta:
                        source = meta["source"]
                        self._sources.add(source)
                        if "content_hash" in meta:
                            self._source_hashes[source] = (
                                meta["content_hash"]
                            )
        except Exception:
            pass

    def ingest(self, path: Path, force: bool = False) -> int:
        """Ingest a markdown file — chunks, embeds, stores.

        Skips re-embedding if the file content hasn't changed
        (based on SHA-256 hash). Use force=True to re-embed anyway.
        Returns the number of chunks stored (0 if skipped).
        """
        file_content = path.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(
            file_content.encode()
        ).hexdigest()[:16]
        source = path.name

        # Skip if content unchanged
        if (
            not force
            and source in self._source_hashes
            and self._source_hashes[source] == content_hash
        ):
            logger.debug("Skipping %s (unchanged)", source)
            return 0

        chunks = chunk_markdown(path)
        if not chunks:
            return 0

        directory = str(path.parent)

        # Remove existing chunks from this source
        self._remove_source(source)

        # Add new chunks with content hash
        ids = [f"{source}:{i}" for i in range(len(chunks))]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "source": c.source,
                "heading_path": c.heading_path,
                "directory": directory,
                "content_hash": content_hash,
            }
            for c in chunks
        ]

        self._collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        self._sources.add(source)
        self._source_hashes[source] = content_hash

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
                        directory=meta.get("directory", ""),
                    )
                )

        return chunks

    def ingest_directory(self, dir_path: Path) -> int:
        """Ingest all .md files from a directory.

        Only re-embeds files whose content has changed.
        Returns total number of newly embedded chunks.
        """
        if not dir_path.exists():
            return 0

        total = 0
        skipped = 0
        for path in sorted(dir_path.glob("*.md")):
            if path.name.startswith("README"):
                continue
            count = self.ingest(path)
            if count:
                total += count
            else:
                skipped += 1

        if skipped:
            logger.info(
                "Knowledge: %d files unchanged (skipped)",
                skipped,
            )
        return total

    def get_sources(self) -> list[str]:
        """Return list of ingested document names."""
        return sorted(self._sources)

    def get_chunks(self, source: str | None = None) -> list[DocumentChunk]:
        """Return stored chunks, optionally filtered by source."""
        kwargs: dict = {"include": ["documents", "metadatas"]}
        if source:
            kwargs["where"] = {"source": source}
        try:
            result = self._collection.get(**kwargs)
        except Exception:
            return []
        chunks: list[DocumentChunk] = []
        if result and result["documents"]:
            for doc, meta in zip(result["documents"], result["metadatas"]):
                chunks.append(
                    DocumentChunk(
                        content=doc,
                        source=meta.get("source", ""),
                        heading_path=meta.get("heading_path", ""),
                        directory=meta.get("directory", ""),
                    )
                )
        return chunks
