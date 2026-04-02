"""SQLite repository for Agent entities."""

from datetime import UTC, datetime
from typing import Any

import aiosqlite

from agent_platform.core.models import Agent, AgentConfig, AgentStatus

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    config TEXT NOT NULL DEFAULT '{}',
    parent_agent_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class SqliteAgentRepo:
    """SQLite-backed repository for agents."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute(CREATE_TABLE_SQL)
        await self._db.commit()

    async def get(self, id: str) -> Agent | None:
        assert self._db is not None
        async with self._db.execute(
            "SELECT * FROM agents WHERE id = ?", (id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_agent(row)

    async def list(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Agent]:
        assert self._db is not None
        sql = "SELECT * FROM agents ORDER BY created_at DESC LIMIT ? OFFSET ?"
        rows: list[Agent] = []
        async with self._db.execute(sql, (limit, offset)) as cursor:
            async for row in cursor:
                rows.append(self._row_to_agent(row))
        return rows

    async def create(self, entity: Agent) -> Agent:
        assert self._db is not None
        await self._db.execute(
            """
            INSERT INTO agents
                (id, name, status, config,
                 parent_agent_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity.id,
                entity.name,
                entity.status.value,
                entity.config.model_dump_json(),
                entity.parent_agent_id,
                entity.created_at.isoformat(),
                entity.updated_at.isoformat(),
            ),
        )
        await self._db.commit()
        return entity

    async def update(self, id: str, entity: Agent) -> Agent:
        assert self._db is not None
        entity.updated_at = datetime.now(UTC)
        await self._db.execute(
            """
            UPDATE agents
            SET name=?, status=?, config=?,
                parent_agent_id=?, updated_at=?
            WHERE id=?
            """,
            (
                entity.name,
                entity.status.value,
                entity.config.model_dump_json(),
                entity.parent_agent_id,
                entity.updated_at.isoformat(),
                id,
            ),
        )
        await self._db.commit()
        return entity

    async def delete(self, id: str) -> bool:
        assert self._db is not None
        cursor = await self._db.execute("DELETE FROM agents WHERE id = ?", (id,))
        await self._db.commit()
        return cursor.rowcount > 0

    async def list_children(self, parent_agent_id: str) -> list[Agent]:
        """List all child agents of a given parent."""
        assert self._db is not None
        rows: list[Agent] = []
        async with self._db.execute(
            "SELECT * FROM agents WHERE parent_agent_id = ? ORDER BY created_at DESC",
            (parent_agent_id,),
        ) as cursor:
            async for row in cursor:
                rows.append(self._row_to_agent(row))
        return rows

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @staticmethod
    def _row_to_agent(row: aiosqlite.Row) -> Agent:
        return Agent(
            id=row[0],
            name=row[1],
            status=AgentStatus(row[2]),
            config=AgentConfig.model_validate_json(row[3]),
            parent_agent_id=row[4],
            created_at=datetime.fromisoformat(row[5]).replace(tzinfo=UTC),
            updated_at=datetime.fromisoformat(row[6]).replace(tzinfo=UTC),
        )
