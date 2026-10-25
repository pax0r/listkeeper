"""Isolated entity-component lookup; only the verified native provider is allowed."""

from ...domain.models import ListItem


class UnsupportedList(ValueError):
    pass


class NativeShoppingList:
    def __init__(self, hass, entity_id: str) -> None:
        self.hass, self.entity_id = hass, entity_id

    def entity(self):
        from homeassistant.components.todo import TodoListEntityFeature
        from homeassistant.components.todo.const import DATA_COMPONENT
        from homeassistant.helpers import entity_registry as er

        registered = er.async_get(self.hass).async_get(self.entity_id)
        component = self.hass.data.get(DATA_COMPONENT)
        entity = component.get_entity(self.entity_id) if component else None
        if (
            registered is None
            or registered.platform != "shopping_list"
            or entity is None
            or not entity.available
            or not callable(getattr(entity, "async_delete_todo_items", None))
            or not entity.supported_features & TodoListEntityFeature.DELETE_TODO_ITEM
        ):
            raise UnsupportedList(
                "Select an available native Shopping List entity supporting UID deletion"
            )
        return entity

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

    async def remove_if_unchanged(
        self, victim: ListItem, keeper: ListItem, expected: list[ListItem]
    ) -> bool:
        # No await between final comparison and UID-specific mutation entry.
        current = self.read_now()
        if (
            victim.uid == keeper.uid
            or victim not in current
            or keeper not in current
            or keeper.completed
            or sorted(current, key=lambda i: i.uid) != sorted(expected, key=lambda i: i.uid)
        ):
            return False
        await self.entity().async_delete_todo_items([victim.uid])
        return True
