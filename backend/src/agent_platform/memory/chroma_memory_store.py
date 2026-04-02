"""ChromaDB-backed memory store."""

from typing import Any

import chromadb

from agent_platform.memory.decay import TimeDecayStrategy
from agent_platform.memory.fake_embeddings import FakeEmbeddingProvider
from agent_platform.memory.models import MemoryEntry, MemoryType, MemoryVisibility

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
        include_public: bool = False,
        exclude_archived: bool = False,
    ) -> list[MemoryEntry]:
        """Semantic search for relevant memories.

        When include_public=True, also returns PUBLIC/TEAM memories
        from other agents (cross-agent memory).
        When exclude_archived=True, filters out archived memories
        (used for context injection but not for explicit recall).
        """
        where: dict[str, Any] | None = None
        conditions: list[dict[str, Any]] = []

        if agent_id and include_public:
            conditions.append(
                {
                    "$or": [
                        {"agent_id": agent_id},
                        {"visibility": MemoryVisibility.PUBLIC.value},
                        {"visibility": MemoryVisibility.TEAM.value},
                    ]
                }
            )
        elif agent_id:
            conditions.append({"agent_id": agent_id})

        if memory_type:
            conditions.append({"memory_type": memory_type.value})

        if exclude_archived:
            conditions.append({"archived": False})

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
        """Archive stale memories below decay threshold or over max count.

        Archived memories are excluded from context injection but remain
        searchable via the recall tool.
        """
        entries = await self.list_by_agent(agent_id, limit=10000)
        if not entries:
            return 0

        # Only consider non-archived entries
        active = [e for e in entries if not e.archived]
        if not active:
            return 0

        # Recompute decay scores
        for entry in active:
            entry.decay_score = self._decay.compute(entry)

        # Find entries to archive
        to_archive: list[str] = []

        # Below threshold
        for entry in active:
            if entry.decay_score < threshold:
                to_archive.append(entry.id)

        # Over max entries — archive lowest-scored beyond limit
        remaining = len(active) - len(to_archive)
        if remaining > max_entries:
            surviving = [e for e in active if e.id not in set(to_archive)]
            surviving.sort(key=lambda e: e.decay_score)
            excess = len(surviving) - max_entries
            for entry in surviving[:excess]:
                to_archive.append(entry.id)

        # Mark as archived (not deleted)
        for mid in to_archive:
            entry = await self.get(mid)
            if entry:
                entry.archived = True
                self._collection.update(
                    ids=[mid],
                    metadatas=[self._entry_to_metadata(entry)],
                )

        return len(to_archive)

    @staticmethod
    def _entry_to_metadata(entry: MemoryEntry) -> dict[str, Any]:
        """Convert entry fields to ChromaDB metadata dict."""
        return {
            "agent_id": entry.agent_id,
            "memory_type": entry.memory_type.value,
            "importance": entry.importance,
            "visibility": entry.visibility.value,
            "created_at": entry.created_at.isoformat(),
            "last_accessed_at": entry.last_accessed_at.isoformat(),
            "access_count": entry.access_count,
            "decay_score": entry.decay_score,
            "archived": entry.archived,
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
            visibility=MemoryVisibility(metadata.get("visibility", "private")),
            created_at=datetime.fromisoformat(
                metadata.get("created_at", datetime.now(UTC).isoformat())
            ).replace(tzinfo=UTC),
            last_accessed_at=datetime.fromisoformat(
                metadata.get("last_accessed_at", datetime.now(UTC).isoformat())
            ).replace(tzinfo=UTC),
            access_count=metadata.get("access_count", 0),
            decay_score=metadata.get("decay_score", 1.0),
            archived=metadata.get("archived", False),
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
