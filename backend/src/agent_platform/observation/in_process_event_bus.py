"""In-process event bus — async queues + optional SQLite persistence."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from agent_platform.observation.events import Event, EventFilter, EventType
from agent_platform.observation.sqlite_event_store import SqliteEventStore


@dataclass
class _Subscription:
    """Internal subscription state."""

    queue: asyncio.Queue[Event] = field(default_factory=asyncio.Queue)
    event_types: list[EventType] | None = None
    agent_id: str | None = None

    def matches(self, event: Event) -> bool:
        """Check if an event matches this subscription's filters."""
        if self.event_types and event.event_type not in self.event_types:
            return False
        if self.agent_id and event.agent_id != self.agent_id:
            return False
        return True


class InProcessEventBus:
    """Event bus using in-memory async queues with optional SQLite persistence."""

    def __init__(self, db_path: str | None = None) -> None:
        self._subscriptions: list[_Subscription] = []
        self._store: SqliteEventStore | None = None
        if db_path:
            self._store = SqliteEventStore(db_path)

    async def initialize(self) -> None:
        """Initialize the SQLite store if configured."""
        if self._store:
            await self._store.initialize()

    async def emit(self, event: Event) -> None:
        """Emit an event to all matching subscribers and persist to SQLite."""
        # Persist first
        if self._store:
            await self._store.insert(event)

        # Deliver to subscribers
        for sub in self._subscriptions:
            if sub.matches(event):
                await sub.queue.put(event)

    def subscribe(
        self,
        event_types: list[EventType] | None = None,
        agent_id: str | None = None,
    ) -> AsyncIterator[Event]:
        """Create a new subscription that yields matching events."""
        sub = _Subscription(event_types=event_types, agent_id=agent_id)
        self._subscriptions.append(sub)
        return self._iter_subscription(sub)

    async def query(self, filters: EventFilter) -> list[Event]:
        """Query persisted events from SQLite."""
        if not self._store:
            return []
        return await self._store.query(filters)

    async def close(self) -> None:
        """Close the SQLite store."""
        if self._store:
            await self._store.close()

    async def _iter_subscription(self, sub: _Subscription) -> AsyncIterator[Event]:
        """Async iterator that yields events from a subscription queue."""
        try:
            while True:
                event = await sub.queue.get()
                yield event
        finally:
            if sub in self._subscriptions:
                self._subscriptions.remove(sub)
