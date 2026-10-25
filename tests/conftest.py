"""Small synthetic fixtures shared by application and SQL integration tests."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from custom_components.pax0r_listkeeper.domain.models import ListItem, State
from custom_components.pax0r_listkeeper.infrastructure.database.store import SqlUnitOfWork


class MemoryUow:
    def __init__(self):
        self.state = State()
        self.fail = False

    async def run(self, work):
        if self.fail:
            raise ConnectionError("synthetic outage")
        pending = deepcopy(self.state)
        result = work(pending)
        self.state = pending
        return result

    async def close(self):
        pass


class FakeList:
    def __init__(self):
        self.items = []
        self.removed = []
        self.fail = False
        self.on_remove = None

    async def read(self):
        return self.items.copy()

    async def remove_if_unchanged(self, victim, keeper, expected):
        if self.fail:
            raise ConnectionError("synthetic remove failure")
        if self.items != expected or victim not in self.items or keeper not in self.items:
            return False
        self.items.remove(victim)
        self.removed.append(victim.uid)
        if self.on_remove:
            self.on_remove()
        return True

    def set(self, uid, name="Milk", completed=False):
        item = ListItem(uid, name, completed)
        self.items = [item if old.uid == uid else old for old in self.items]
        if not any(old.uid == uid for old in self.items):
            self.items.append(item)


@pytest.fixture
def memory():
    return MemoryUow()


@pytest.fixture
def shopping():
    return FakeList()


@pytest.fixture
def now():
    return datetime(2026, 8, 1, 12, tzinfo=UTC)


@pytest.fixture
async def sql(tmp_path):
    uow = SqlUnitOfWork("sqlite:///" + str(tmp_path / "shopping.db"))
    uow.initialize()
    yield uow
    await uow.close()
