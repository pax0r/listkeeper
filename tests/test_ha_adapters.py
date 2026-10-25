"""Adapter contract tests with injected HA fakes; no claim of a real HA boot."""

import asyncio
import sys
from enum import IntFlag, StrEnum
from types import ModuleType, SimpleNamespace

import pytest

from custom_components.pax0r_listkeeper.domain.models import ListItem
from custom_components.pax0r_listkeeper.infrastructure.ha.database_config import database_url
from custom_components.pax0r_listkeeper.infrastructure.ha.runtime import Runtime
from custom_components.pax0r_listkeeper.infrastructure.ha.shopping_list import (
    NativeShoppingList,
    UnsupportedList,
)


class Feature(IntFlag):
    DELETE_TODO_ITEM = 2


class Status(StrEnum):
    COMPLETED = "completed"
    NEEDS_ACTION = "needs_action"


@pytest.fixture
def ha_modules(monkeypatch, tmp_path):
    registry = SimpleNamespace(platform="shopping_list")
    entity = SimpleNamespace(available=True, supported_features=2, todo_items=[])

    async def remove(uids):
        entity.todo_items = [i for i in entity.todo_items if i.uid not in uids]

    entity.async_delete_todo_items = remove
    definitions = {
        "homeassistant": {},
        "homeassistant.components": {},
        "homeassistant.components.todo": {
            "TodoItemStatus": Status,
            "TodoListEntityFeature": Feature,
        },
        "homeassistant.components.todo.const": {"DATA_COMPONENT": "todo"},
        "homeassistant.helpers": {},
        "homeassistant.helpers.entity_registry": {
            "async_get": lambda h: SimpleNamespace(async_get=lambda identity: registry)
        },
        "homeassistant.helpers.recorder": {"get_instance": lambda h: h.recorder},
    }
    for name, attributes in definitions.items():
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    hass = SimpleNamespace(
        data={"todo": SimpleNamespace(get_entity=lambda identity: entity)},
        config=SimpleNamespace(path=lambda file: str(tmp_path / file)),
        recorder=SimpleNamespace(db_url="sqlite:///recorder.db"),
    )
    return hass, entity, registry


def set_items(entity, *items):
    entity.todo_items = [
        SimpleNamespace(
            uid=i.uid,
            summary=i.name,
            status=Status.COMPLETED if i.completed else Status.NEEDS_ACTION,
        )
        for i in items
    ]


@pytest.mark.parametrize("completed", [False, True])
async def test_uid_collision_with_name_does_not_delete_wrong_item(ha_modules, completed):
    hass, entity, _ = ha_modules
    victim, keeper, collision = (
        ListItem("a", "Milk", completed),
        ListItem("b", "milk", completed),
        ListItem("c", "a", False),
    )
    set_items(entity, collision, victim, keeper)
    adapter = NativeShoppingList(hass, "todo.shopping_list")
    expected = await adapter.read()
    assert await adapter.remove_if_unchanged(victim, keeper, expected)
    assert {i.uid for i in await adapter.read()} == {"b", "c"}


async def test_adapter_never_removes_active_item_for_completed_survivor(ha_modules):
    hass, entity, _ = ha_modules
    victim, keeper = ListItem("a", "Milk", False), ListItem("b", "milk", True)
    set_items(entity, victim, keeper)
    adapter = NativeShoppingList(hass, "todo.shopping_list")
    assert not await adapter.remove_if_unchanged(victim, keeper, await adapter.read())
    assert len(await adapter.read()) == 2


async def test_local_todo_lock_and_metadata_guard(ha_modules):
    hass, entity, registry = ha_modules
    registry.platform = "local_todo"
    entity._calendar_lock = asyncio.Lock()
    entity.async_subscribe_updates = lambda listener: lambda: None
    victim, keeper = ListItem("a", "Soap", False), ListItem("b", "Soap", False)
    set_items(entity, victim, keeper)
    adapter = NativeShoppingList(hass, "todo.local")
    entity._calendar = SimpleNamespace(
        todos=[
            SimpleNamespace(
                uid=i.uid, summary=i.name, status="NEEDS-ACTION", due=None, description=None
            )
            for i in (victim, keeper)
        ]
    )
    assert callable(adapter.subscribe(lambda items: None))
    expected = await adapter.read()
    async with entity._calendar_lock:
        assert not await adapter.remove_if_unchanged(victim, keeper, expected)
    entity.todo_items[0].description = "Keep this note"
    assert not await adapter.remove_if_unchanged(victim, keeper, expected)
    entity.todo_items[0].description = None
    entity._calendar.todos[0].summary = "Renamed but not published"
    assert not await adapter.remove_if_unchanged(victim, keeper, expected)
    entity._calendar.todos[0].summary = "Soap"
    assert await adapter.remove_if_unchanged(victim, keeper, expected)


async def test_unknown_provider_is_refused_even_with_delete_capability(ha_modules):
    hass, _, registry = ha_modules
    registry.platform = "unverified_provider"
    with pytest.raises(UnsupportedList):
        await NativeShoppingList(hass, "todo.other").read()


async def test_adapter_refuses_changed_state_and_non_native_provider(ha_modules):
    hass, entity, registry = ha_modules
    victim, keeper = ListItem("a", "Milk", False), ListItem("b", "milk", False)
    set_items(entity, victim, keeper)
    adapter = NativeShoppingList(hass, "todo.shopping_list")
    expected = await adapter.read()
    set_items(entity, victim, ListItem("b", "Other", False))
    assert not await adapter.remove_if_unchanged(victim, keeper, expected)
    registry.platform = "local_todo"
    with pytest.raises(UnsupportedList):
        await adapter.read()


@pytest.mark.parametrize(
    "recorder,manual,expected",
    [
        (SimpleNamespace(db_url="sqlite:///recorder.db"), "", "sqlite"),
        (SimpleNamespace(), "", "sqlite"),
        (
            SimpleNamespace(db_url=object()),
            "postgresql://u:secret@localhost/test",
            "postgresql+psycopg2",
        ),
        (SimpleNamespace(db_url="mysql://u:secret@localhost/test"), "", "mysql+pymysql"),
    ],
)
def test_database_detection_is_guarded(ha_modules, recorder, manual, expected):
    hass, _, _ = ha_modules
    hass.recorder = recorder
    url = database_url(hass, manual)
    assert url.startswith(expected + ":")
    if expected == "sqlite":
        assert url.endswith("pax0r_listkeeper.db")


def test_recorder_sqlite_cannot_be_used_as_owned_file(ha_modules):
    hass, _, _ = ha_modules
    hass.recorder.db_url = "sqlite:///" + hass.config.path("pax0r_listkeeper.db")
    with pytest.raises(ValueError):
        database_url(hass)


async def test_runtime_coalesces_self_events_and_unloads(memory, shopping, now):
    tasks = []

    def create_task(coro):
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    shopping.read_now = lambda: shopping.items.copy()
    hass = SimpleNamespace(async_create_task=create_task)
    runtime = Runtime(hass, memory, shopping, "list", True)
    shopping.set("old")
    await runtime.sync()
    shopping.set("new")
    runtime.changed(SimpleNamespace(data={"action": "add", "item": {"id": "new"}}))
    runtime.changed(SimpleNamespace(data={"entity_id": "todo.shopping_list"}))
    shopping.on_remove = lambda: runtime.changed(SimpleNamespace(data={"action": "remove"}))
    await asyncio.gather(*tasks)
    assert [i.uid for i in shopping.items] == ["new"]
    assert not memory.state.purchases
    await runtime.close()
    assert not runtime.tasks
    await runtime.close()  # HA stop followed by config entry unload is safe.


async def test_runtime_failure_does_not_cancel_recovered_purchase(memory, shopping, now):
    shopping.read_now = lambda: shopping.items.copy()
    hass = SimpleNamespace(async_create_task=asyncio.create_task)
    runtime = Runtime(hass, memory, shopping, "list", True)
    shopping.set("a")
    await runtime.sync()
    shopping.set("a", completed=True)
    await runtime.sync(now, shopping.items.copy())
    memory.fail = True
    shopping.set("a", completed=False)
    await runtime.sync(now, shopping.items.copy())
    assert runtime.error
    memory.fail = False
    await runtime.sync()
    assert next(iter(memory.state.purchases.values())).status == "confirmed"
    await runtime.close()
