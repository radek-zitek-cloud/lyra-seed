"""SQLite repository for AgentMessage entities."""

from datetime import UTC, datetime
from typing import Any

import aiosqlite

from agent_platform.core.models import AgentMessage, MessageType

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_messages (
    id TEXT PRIMARY KEY,
    from_agent_id TEXT NOT NULL,
    to_agent_id TEXT NOT NULL,
    content TEXT NOT NULL,
    message_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    in_reply_to TEXT
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_msg_to ON agent_messages (to_agent_id);",
    "CREATE INDEX IF NOT EXISTS idx_msg_from ON agent_messages (from_agent_id);",
    "CREATE INDEX IF NOT EXISTS idx_msg_ts ON agent_messages (timestamp);",
]


class SqliteMessageRepo:
    """SQLite-backed repository for inter-agent messages."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute(CREATE_TABLE_SQL)
        for idx in CREATE_INDEXES_SQL:
            await self._db.execute(idx)
        await self._db.commit()

    async def create(self, msg: AgentMessage) -> AgentMessage:
        assert self._db is not None
        await self._db.execute(
            """
            INSERT INTO agent_messages
                (id, from_agent_id, to_agent_id, content,
                 message_type, timestamp, in_reply_to)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg.id,
                msg.from_agent_id,
                msg.to_agent_id,
                msg.content,
                msg.message_type.value,
                msg.timestamp.isoformat(),
                msg.in_reply_to,
            ),
        )
        await self._db.commit()
        return msg

    async def get(self, id: str) -> AgentMessage | None:
        assert self._db is not None
        async with self._db.execute(
            "SELECT * FROM agent_messages WHERE id = ?", (id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_message(row)

    async def list_for_agent(
        self,
        agent_id: str,
        direction: str = "all",
        message_type: MessageType | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[AgentMessage]:
        """List messages for an agent.

        direction: 'inbox' (to), 'sent' (from), 'all' (both)
        """
        assert self._db is not None
        clauses: list[str] = []
        params: list[Any] = []

        if direction == "inbox":
            clauses.append("to_agent_id = ?")
            params.append(agent_id)
        elif direction == "sent":
            clauses.append("from_agent_id = ?")
            params.append(agent_id)
        else:
            clauses.append("(to_agent_id = ? OR from_agent_id = ?)")
            params.extend([agent_id, agent_id])

        if message_type:
            clauses.append("message_type = ?")
            params.append(message_type.value)

        if since:
            clauses.append("timestamp > ?")
            params.append(since)

        where = " AND ".join(clauses)
        sql = (
            f"SELECT * FROM agent_messages WHERE {where} "
            f"ORDER BY timestamp ASC LIMIT ?"
        )
        params.append(limit)

        rows: list[AgentMessage] = []
        async with self._db.execute(sql, params) as cursor:
            async for row in cursor:
                rows.append(self._row_to_message(row))
        return rows

    async def list_between(
        self,
        agent_a: str,
        agent_b: str,
        limit: int = 100,
    ) -> list[AgentMessage]:
        """List messages between two agents."""
        assert self._db is not None
        sql = """
            SELECT * FROM agent_messages
            WHERE (from_agent_id = ? AND to_agent_id = ?)
               OR (from_agent_id = ? AND to_agent_id = ?)
            ORDER BY timestamp ASC LIMIT ?
        """
        rows: list[AgentMessage] = []
        async with self._db.execute(
            sql, (agent_a, agent_b, agent_b, agent_a, limit)
        ) as cursor:
            async for row in cursor:
                rows.append(self._row_to_message(row))
        return rows

    async def delete(self, id: str) -> bool:
        assert self._db is not None
        cursor = await self._db.execute(
            "DELETE FROM agent_messages WHERE id = ?", (id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @staticmethod
    def _row_to_message(row: aiosqlite.Row) -> AgentMessage:
        return AgentMessage(
            id=row[0],
            from_agent_id=row[1],
            to_agent_id=row[2],
            content=row[3],
            message_type=MessageType(row[4]),
            timestamp=datetime.fromisoformat(row[5]).replace(tzinfo=UTC),
            in_reply_to=row[6],
        )
