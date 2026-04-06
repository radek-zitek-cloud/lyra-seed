"""In-process event bus — async queues + optional SQLite persistence."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from agent_platform.observation.events import Event, EventFilter, EventType
from agent_platform.observation.sqlite_event_store import SqliteEventStore

# Sentinel object to signal subscription shutdown
_SHUTDOWN = object()


@dataclass
class _Subscription:
    """Internal subscription state."""

    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    event_types: list[EventType] | None = None
    agent_id: str | None = None
    closed: bool = False

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
        self._closed = False
        if db_path:
            self._store = SqliteEventStore(db_path)

    async def initialize(self) -> None:
        """Initialize the SQLite store if configured."""
        if self._store:
            await self._store.initialize()

    async def emit(self, event: Event) -> None:
        """Emit an event to all matching subscribers and persist to SQLite."""
        if self._closed:
            return
        # Persist first
        if self._store:
            await self._store.insert(event)

        # Deliver to subscribers
        for sub in self._subscriptions:
            if sub.matches(event):
                sub.queue.put_nowait(event)

    @property
    def is_closed(self) -> bool:
        return self._closed

    def subscribe(
        self,
        event_types: list[EventType] | None = None,
        agent_id: str | None = None,
    ) -> AsyncIterator[Event]:
        """Create a new subscription that yields matching events."""
        sub = _Subscription(
            event_types=event_types, agent_id=agent_id, closed=self._closed
        )
        self._subscriptions.append(sub)
        return self._iter_subscription(sub)

    async def query(self, filters: EventFilter) -> list[Event]:
        """Query persisted events from SQLite."""
        if not self._store:
            return []
        return await self._store.query(filters)

    async def close(self) -> None:
        """Cancel all subscriptions and close the SQLite store."""
        self._closed = True
        # Unblock all waiting subscribers immediately
        for sub in list(self._subscriptions):
            sub.closed = True
            sub.queue.put_nowait(_SHUTDOWN)
        self._subscriptions.clear()

        if self._store:
            await self._store.close()

    async def delete_agent_events(self, agent_id: str) -> int:
        """Delete all persisted events for an agent."""
        if self._store:
            return await self._store.delete_by_agent(agent_id)
        return 0

    async def _iter_subscription(self, sub: _Subscription) -> AsyncIterator[Event]:
        """Async iterator that yields events from a subscription queue."""
        try:
            while not sub.closed:
                item = await sub.queue.get()
                if item is _SHUTDOWN or item is None or sub.closed:
                    return
                yield item
        finally:
            if sub in self._subscriptions:
                self._subscriptions.remove(sub)
