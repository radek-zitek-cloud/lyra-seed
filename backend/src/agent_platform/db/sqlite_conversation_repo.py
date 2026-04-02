"""SQLite repository for Conversation entities."""

import json
from typing import Any

import aiosqlite

from agent_platform.core.models import Conversation
from agent_platform.llm.models import Message

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    messages TEXT NOT NULL DEFAULT '[]'
);
"""


class SqliteConversationRepo:
    """SQLite-backed repository for conversations."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute(CREATE_TABLE_SQL)
        await self._db.commit()

    async def get(self, id: str) -> Conversation | None:
        assert self._db is not None
        async with self._db.execute(
            "SELECT * FROM conversations WHERE id = ?", (id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_conversation(row)

    async def list(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Conversation]:
        assert self._db is not None
        clauses: list[str] = []
        params: list[Any] = []

        if filters and "agent_id" in filters:
            clauses.append("agent_id = ?")
            params.append(filters["agent_id"])

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM conversations WHERE {where} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows: list[Conversation] = []
        async with self._db.execute(sql, params) as cursor:
            async for row in cursor:
                rows.append(self._row_to_conversation(row))
        return rows

    async def create(self, entity: Conversation) -> Conversation:
        assert self._db is not None
        messages_json = json.dumps([m.model_dump(mode="json") for m in entity.messages])
        await self._db.execute(
            "INSERT INTO conversations (id, agent_id, messages) VALUES (?, ?, ?)",
            (entity.id, entity.agent_id, messages_json),
        )
        await self._db.commit()
        return entity

    async def update(self, id: str, entity: Conversation) -> Conversation:
        assert self._db is not None
        messages_json = json.dumps([m.model_dump(mode="json") for m in entity.messages])
        await self._db.execute(
            "UPDATE conversations SET agent_id=?, messages=? WHERE id=?",
            (entity.agent_id, messages_json, id),
        )
        await self._db.commit()
        return entity

    async def delete(self, id: str) -> bool:
        assert self._db is not None
        cursor = await self._db.execute("DELETE FROM conversations WHERE id = ?", (id,))
        await self._db.commit()
        return cursor.rowcount > 0

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @staticmethod
    def _row_to_conversation(row: aiosqlite.Row) -> Conversation:
        messages_data = json.loads(row[2])
        messages = [Message.model_validate(m) for m in messages_data]
        return Conversation(
            id=row[0],
            agent_id=row[1],
            messages=messages,
        )
