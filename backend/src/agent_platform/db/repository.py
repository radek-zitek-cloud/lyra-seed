"""Generic repository protocol."""

from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class Repository(Protocol[T]):
    """Abstract CRUD repository for any entity type."""

    async def get(self, id: str) -> T | None: ...

    async def list(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[T]: ...

    async def create(self, entity: T) -> T: ...

    async def update(self, id: str, entity: T) -> T: ...

    async def delete(self, id: str) -> bool: ...
