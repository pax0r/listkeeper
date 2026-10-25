"""Isolated access to verified Shopping List and Local To-do providers."""

import asyncio
from datetime import date, datetime, timedelta

from ...domain.models import ListItem


class UnsupportedList(ValueError):
    pass


class NativeShoppingList:
    def __init__(self, hass, entity_id: str) -> None:
        self.hass, self.entity_id = hass, entity_id

    def entity(self, require_available: bool = True):
        from homeassistant.components.todo import TodoListEntityFeature
        from homeassistant.components.todo.const import DATA_COMPONENT
        from homeassistant.helpers import entity_registry as er

        registered = er.async_get(self.hass).async_get(self.entity_id)
        component = self.hass.data.get(DATA_COMPONENT)
        entity = component.get_entity(self.entity_id) if component else None
        if (
            registered is None
            or registered.platform not in {"shopping_list", "local_todo"}
            or entity is None
            or (require_available and not entity.available)
            or not callable(getattr(entity, "async_delete_todo_items", None))
            or not entity.supported_features & TodoListEntityFeature.DELETE_TODO_ITEM
        ):
            raise UnsupportedList(
                "Select an available Shopping List or Local To-do entity supporting UID deletion"
            )
        if registered.platform == "local_todo" and not isinstance(
            getattr(entity, "_calendar_lock", None), asyncio.Lock
        ):
            raise UnsupportedList("This Local To-do version does not provide a verified edit lock")
        return entity

    def subscribe(self, listener):
        """Receive item changes even when the entity's active-item count is unchanged."""
        entity = self.entity(require_available=False)
        subscribe = getattr(entity, "async_subscribe_updates", None)
        if not callable(subscribe):
            raise UnsupportedList("The list does not support item update subscriptions")
        return subscribe(listener)

    def read_now(self) -> list[ListItem]:
        from homeassistant.components.todo import TodoItemStatus

        items = self.entity().todo_items
        if items is None:
            raise UnsupportedList("The list state is unavailable")
        result = []
        for item in items:
            if (
                not isinstance(item.uid, str)
                or not item.uid
                or not isinstance(item.summary, str)
                or item.status not in (TodoItemStatus.COMPLETED, TodoItemStatus.NEEDS_ACTION)
            ):
                raise UnsupportedList("The list does not provide stable UIDs and statuses")
            result.append(ListItem(item.uid, item.summary, item.status == TodoItemStatus.COMPLETED))
        if len({i.uid for i in result}) != len(result):
            raise UnsupportedList("The list provides duplicate UIDs")
        return result

    async def read(self) -> list[ListItem]:
        return self.read_now()

    def _calendar_matches(self, entity, current: list[ListItem]) -> bool:
        """Refuse the gap between a calendar edit and publication of todo_items."""
        calendar = getattr(entity, "_calendar", None)
        if calendar is None:
            return False
        published = {item.uid: item for item in entity.todo_items or []}
        actual = []
        for todo in calendar.todos:
            status = getattr(todo.status, "value", todo.status) or "NEEDS-ACTION"
            if status not in {"NEEDS-ACTION", "IN-PROCESS", "COMPLETED", "CANCELLED"}:
                return False
            actual.append(
                ListItem(todo.uid, todo.summary or "", status in {"COMPLETED", "CANCELLED"})
            )
            item = published.get(todo.uid)
            due = todo.due
            if isinstance(due, date) and not isinstance(due, datetime):
                due -= timedelta(days=1)  # Local To-do stores exclusive all-day due dates.
            if (
                item is None
                or due != getattr(item, "due", None)
                or todo.description != getattr(item, "description", None)
            ):
                return False
        return sorted(actual, key=lambda item: item.uid) == sorted(
            current, key=lambda item: item.uid
        )

    async def remove_if_unchanged(
        self, victim: ListItem, keeper: ListItem, expected: list[ListItem]
    ) -> bool:
        # No await between final comparison and UID-specific mutation entry.
        current = self.read_now()
        entity = self.entity()
        lock = getattr(entity, "_calendar_lock", None)
        source = {item.uid: item for item in entity.todo_items or []}
        rich_fields = ("due", "description")
        incompatible = any(
            getattr(source.get(victim.uid), field, None)
            != getattr(source.get(keeper.uid), field, None)
            for field in rich_fields
        )
        if (
            victim.uid == keeper.uid
            or victim not in current
            or keeper not in current
            or (keeper.completed and not victim.completed)
            or (lock is not None and lock.locked())
            or (lock is not None and not self._calendar_matches(entity, current))
            or incompatible
            or sorted(current, key=lambda i: i.uid) != sorted(expected, key=lambda i: i.uid)
        ):
            return False
        await entity.async_delete_todo_items([victim.uid])
        return True
