"""Generic strategy protocol."""

from typing import Protocol, TypeVar, runtime_checkable

TInput = TypeVar("TInput", contravariant=True)
TOutput = TypeVar("TOutput", covariant=True)


@runtime_checkable
class Strategy(Protocol[TInput, TOutput]):
    """Abstract strategy pattern — transform input to output."""

    async def execute(self, input: TInput) -> TOutput: ...
