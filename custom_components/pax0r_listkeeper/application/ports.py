"""Boundary interfaces. Transactions run through a worker-backed Unit of Work."""

from collections.abc import Callable
from typing import Protocol, TypeVar

from ..domain.models import ListItem, State

T = TypeVar("T")


class UnitOfWork(Protocol):
    async def run(self, work: Callable[[State], T]) -> T: ...
    async def close(self) -> None: ...


class ShoppingList(Protocol):
    async def read(self) -> list[ListItem]: ...

    async def remove_if_unchanged(
        self, victim: ListItem, keeper: ListItem, expected: list[ListItem]
    ) -> bool: ...


class ShoppingAnalytics(Protocol):
    def dashboard(self, state: State, days: int | None = None) -> dict: ...
