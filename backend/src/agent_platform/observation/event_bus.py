"""EventBus protocol."""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from agent_platform.observation.events import Event, EventFilter, EventType


@runtime_checkable
class EventBus(Protocol):
    """Abstract interface for the event bus."""

    async def emit(self, event: Event) -> None: ...

    def subscribe(
        self,
        event_types: list[EventType] | None = None,
        agent_id: str | None = None,
    ) -> AsyncIterator[Event]: ...

    async def query(self, filters: EventFilter) -> list[Event]: ...
