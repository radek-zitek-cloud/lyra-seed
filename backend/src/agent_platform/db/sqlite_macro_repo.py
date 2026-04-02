"""SQLite repository for PromptMacro entities."""

import json
from typing import Any

import aiosqlite

from agent_platform.tools.prompt_macro import PromptMacro

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prompt_macros (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    template TEXT NOT NULL,
    parameters TEXT NOT NULL DEFAULT '{}',
    output_instructions TEXT NOT NULL DEFAULT ''
);
"""


class SqliteMacroRepo:
    """SQLite-backed repository for prompt macros."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute(CREATE_TABLE_SQL)
        await self._db.commit()

    async def get(self, id: str) -> PromptMacro | None:
        assert self._db is not None
        async with self._db.execute(
            "SELECT * FROM prompt_macros WHERE id = ?", (id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_macro(row)

    async def list(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PromptMacro]:
        assert self._db is not None
        sql = "SELECT * FROM prompt_macros LIMIT ? OFFSET ?"
        rows: list[PromptMacro] = []
        async with self._db.execute(sql, (limit, offset)) as cursor:
            async for row in cursor:
                rows.append(self._row_to_macro(row))
        return rows

    async def create(self, entity: PromptMacro) -> PromptMacro:
        assert self._db is not None
        await self._db.execute(
            """
            INSERT INTO prompt_macros
                (id, name, description, template,
                 parameters, output_instructions)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entity.id,
                entity.name,
                entity.description,
                entity.template,
                json.dumps(entity.parameters),
                entity.output_instructions,
            ),
        )
        await self._db.commit()
        return entity

    async def update(self, id: str, entity: PromptMacro) -> PromptMacro:
        assert self._db is not None
        await self._db.execute(
            """
            UPDATE prompt_macros
            SET name=?, description=?, template=?,
                parameters=?, output_instructions=?
            WHERE id=?
            """,
            (
                entity.name,
                entity.description,
                entity.template,
                json.dumps(entity.parameters),
                entity.output_instructions,
                id,
            ),
        )
        await self._db.commit()
        return entity

    async def delete(self, id: str) -> bool:
        assert self._db is not None
        cursor = await self._db.execute("DELETE FROM prompt_macros WHERE id = ?", (id,))
        await self._db.commit()
        return cursor.rowcount > 0

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @staticmethod
    def _row_to_macro(row: aiosqlite.Row) -> PromptMacro:
        return PromptMacro(
            id=row[0],
            name=row[1],
            description=row[2],
            template=row[3],
            parameters=json.loads(row[4]),
            output_instructions=row[5],
        )
