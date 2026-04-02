"""ChromaDB-backed memory store."""

from typing import Any

import chromadb

from agent_platform.memory.decay import TimeDecayStrategy
from agent_platform.memory.fake_embeddings import FakeEmbeddingProvider
from agent_platform.memory.models import MemoryEntry, MemoryType

COLLECTION_NAME = "agent_memories"


class ChromaMemoryStore:
    """Memory storage backed by ChromaDB with built-in similarity search."""

    def __init__(
        self,
        persist_dir: str | None = None,
        embedding_fn: Any = None,
        decay_strategy: TimeDecayStrategy | None = None,
    ) -> None:
        if persist_dir:
            self._client = chromadb.PersistentClient(path=persist_dir)
        else:
            self._client = chromadb.Client()

        self._embedding_fn = embedding_fn or FakeEmbeddingProvider()
        self._decay = decay_strategy or TimeDecayStrategy()
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def embedding_fn(self):
        """Access the embedding function (for setting agent_id etc)."""
        return self._embedding_fn

    async def add(self, entry: MemoryEntry) -> None:
        """Store a memory entry."""
        self._collection.add(
            ids=[entry.id],
            documents=[entry.content],
            metadatas=[self._entry_to_metadata(entry)],
        )

    async def get(self, id: str) -> MemoryEntry | None:
        """Get a memory entry by ID."""
        result = self._collection.get(ids=[id], include=["documents", "metadatas"])
        if not result["ids"]:
            return None
        return self._result_to_entry(
            result["ids"][0],
            result["documents"][0],  # type: ignore[index]
            result["metadatas"][0],  # type: ignore[index]
        )

    async def list_by_agent(self, agent_id: str, limit: int = 100) -> list[MemoryEntry]:
        """List all memories for an agent."""
        result = self._collection.get(
            where={"agent_id": agent_id},
            include=["documents", "metadatas"],
            limit=limit,
        )
        return self._results_to_entries(result)

    async def search(
        self,
        query: str,
        agent_id: str | None = None,
        memory_type: MemoryType | None = None,
        top_k: int = 5,
    ) -> list[MemoryEntry]:
        """Semantic search for relevant memories."""
        where: dict[str, Any] | None = None
        conditions: list[dict[str, Any]] = []

        if agent_id:
            conditions.append({"agent_id": agent_id})
        if memory_type:
            conditions.append({"memory_type": memory_type.value})

        if len(conditions) > 1:
            where = {"$and": conditions}
        elif len(conditions) == 1:
            where = conditions[0]

        try:
            result = self._collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas"],
            )
        except Exception:
            # ChromaDB raises if collection is empty or no matches
            return []

        if not result["ids"] or not result["ids"][0]:
            return []

        entries: list[MemoryEntry] = []
        for i, id_ in enumerate(result["ids"][0]):
            doc = result["documents"][0][i]  # type: ignore[index]
            meta = result["metadatas"][0][i]  # type: ignore[index]
            entries.append(self._result_to_entry(id_, doc, meta))
        return entries

    async def delete(self, id: str) -> bool:
        """Delete a memory entry."""
        try:
            self._collection.delete(ids=[id])
            return True
        except Exception:
            return False

    async def update_access(self, id: str) -> None:
        """Update last_accessed_at, increment access_count, recompute decay."""
        entry = await self.get(id)
        if entry is None:
            return
        from datetime import UTC, datetime

        entry.last_accessed_at = datetime.now(UTC)
        entry.access_count += 1
        entry.decay_score = self._decay.compute(entry)
        self._collection.update(
            ids=[id],
            metadatas=[self._entry_to_metadata(entry)],
        )

    async def prune(
        self,
        agent_id: str,
        threshold: float = 0.1,
        max_entries: int = 500,
    ) -> int:
        """Delete stale memories below decay threshold or over max count."""
        entries = await self.list_by_agent(agent_id, limit=10000)
        if not entries:
            return 0

        # Recompute decay scores
        for entry in entries:
            entry.decay_score = self._decay.compute(entry)

        # Find entries to delete
        to_delete: list[str] = []

        # Below threshold
        for entry in entries:
            if entry.decay_score < threshold:
                to_delete.append(entry.id)

        # Over max entries — delete lowest-scored beyond limit
        if len(entries) - len(to_delete) > max_entries:
            surviving = [e for e in entries if e.id not in set(to_delete)]
            surviving.sort(key=lambda e: e.decay_score)
            excess = len(surviving) - max_entries
            for entry in surviving[:excess]:
                to_delete.append(entry.id)

        if to_delete:
            self._collection.delete(ids=to_delete)

        return len(to_delete)

    @staticmethod
    def _entry_to_metadata(entry: MemoryEntry) -> dict[str, Any]:
        """Convert entry fields to ChromaDB metadata dict."""
        return {
            "agent_id": entry.agent_id,
            "memory_type": entry.memory_type.value,
            "importance": entry.importance,
            "created_at": entry.created_at.isoformat(),
            "last_accessed_at": entry.last_accessed_at.isoformat(),
            "access_count": entry.access_count,
            "decay_score": entry.decay_score,
        }

    @staticmethod
    def _result_to_entry(
        id_: str, document: str, metadata: dict[str, Any]
    ) -> MemoryEntry:
        """Convert ChromaDB result to MemoryEntry."""
        from datetime import UTC, datetime

        return MemoryEntry(
            id=id_,
            agent_id=metadata["agent_id"],
            content=document,
            memory_type=MemoryType(metadata["memory_type"]),
            importance=metadata.get("importance", 0.5),
            created_at=datetime.fromisoformat(
                metadata.get("created_at", datetime.now(UTC).isoformat())
            ).replace(tzinfo=UTC),
            last_accessed_at=datetime.fromisoformat(
                metadata.get("last_accessed_at", datetime.now(UTC).isoformat())
            ).replace(tzinfo=UTC),
            access_count=metadata.get("access_count", 0),
            decay_score=metadata.get("decay_score", 1.0),
        )

    @staticmethod
    def _results_to_entries(result: dict) -> list[MemoryEntry]:
        """Convert ChromaDB get results to list of MemoryEntry."""
        entries: list[MemoryEntry] = []
        for i, id_ in enumerate(result["ids"]):
            doc = result["documents"][i]  # type: ignore[index]
            meta = result["metadatas"][i]  # type: ignore[index]
            entries.append(ChromaMemoryStore._result_to_entry(id_, doc, meta))
        return entries
