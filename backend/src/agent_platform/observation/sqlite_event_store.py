"""SQLite persistence for events."""

import json
from datetime import UTC, datetime
from uuid import UUID

import aiosqlite

from agent_platform.observation.events import Event, EventFilter, EventType

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    parent_event_id TEXT,
    module TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    duration_ms INTEGER
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_events_agent_id ON events (agent_id);",
    "CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type);",
    "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp);",
]


class SqliteEventStore:
    """Append-only event store backed by SQLite."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Create the events table if it doesn't exist."""
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute(CREATE_TABLE_SQL)
        for idx_sql in CREATE_INDEXES_SQL:
            await self._db.execute(idx_sql)
        await self._db.commit()

    async def insert(self, event: Event) -> None:
        """Insert an event into the store."""
        assert self._db is not None
        await self._db.execute(
            """
            INSERT INTO events
                (id, timestamp, agent_id, event_type,
                 parent_event_id, module, payload, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(event.id),
                event.timestamp.isoformat(),
                event.agent_id,
                event.event_type.value,
                str(event.parent_event_id) if event.parent_event_id else None,
                event.module,
                json.dumps(event.payload),
                event.duration_ms,
            ),
        )
        await self._db.commit()

    async def query(self, filters: EventFilter) -> list[Event]:
        """Query events matching the given filters."""
        assert self._db is not None
        clauses: list[str] = []
        params: list[str | int | float] = []

        if filters.agent_id is not None:
            clauses.append("agent_id = ?")
            params.append(filters.agent_id)

        if filters.event_types is not None:
            placeholders = ",".join("?" for _ in filters.event_types)
            clauses.append(f"event_type IN ({placeholders})")
            params.extend(et.value for et in filters.event_types)

        if filters.time_from is not None:
            clauses.append("timestamp >= ?")
            params.append(filters.time_from.isoformat())

        if filters.time_to is not None:
            clauses.append("timestamp <= ?")
            params.append(filters.time_to.isoformat())

        if filters.module is not None:
            clauses.append("module = ?")
            params.append(filters.module)

        if filters.parent_event_id is not None:
            clauses.append("parent_event_id = ?")
            params.append(str(filters.parent_event_id))

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM events WHERE {where} ORDER BY timestamp ASC"

        rows: list[Event] = []
        async with self._db.execute(sql, params) as cursor:
            async for row in cursor:
                rows.append(self._row_to_event(row))
        return rows

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @staticmethod
    def _row_to_event(row: aiosqlite.Row) -> Event:
        """Convert a database row to an Event model."""
        return Event(
            id=UUID(row[0]),
            timestamp=datetime.fromisoformat(row[1]).replace(tzinfo=UTC),
            agent_id=row[2],
            event_type=EventType(row[3]),
            parent_event_id=UUID(row[4]) if row[4] else None,
            module=row[5],
            payload=json.loads(row[6]),
            duration_ms=row[7],
        )
