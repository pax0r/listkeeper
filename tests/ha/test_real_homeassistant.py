"""Real HA smoke/compatibility tests, executed separately on Linux in CI."""

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components.todo import TodoItem, TodoItemStatus  # noqa: E402
from homeassistant.setup import async_setup_component  # noqa: E402

from custom_components.pax0r_listkeeper.infrastructure.ha.shopping_list import (  # noqa: E402
    NativeShoppingList,
)

DOMAIN = "pax0r_listkeeper"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_native_entity_adapter(hass):
    assert await async_setup_component(hass, "shopping_list", {})
    result = await hass.config_entries.flow.async_init("shopping_list", context={"source": "user"})
    if result["type"] == "form":
        await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    entities = hass.states.async_entity_ids("todo")
    assert entities
    adapter = NativeShoppingList(hass, entities[0])
    await adapter.entity().async_create_todo_item(
        TodoItem(summary="A", status=TodoItemStatus.NEEDS_ACTION)
    )
    await adapter.entity().async_create_todo_item(
        TodoItem(summary="A", status=TodoItemStatus.NEEDS_ACTION)
    )
    items = await adapter.read()
    assert len(items) == 2
    assert await adapter.remove_if_unchanged(items[0], items[1], items)
    assert [i.uid for i in await adapter.read()] == [items[1].uid]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_config_flow_panel_websocket_and_unload(hass, hass_ws_client):
    assert await async_setup_component(hass, "shopping_list", {})
    flow = await hass.config_entries.flow.async_init("shopping_list", context={"source": "user"})
    if flow["type"] == "form":
        await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    await hass.async_block_till_done()
    entity_id = hass.states.async_entity_ids("todo")[0]
    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={
            "entity_id": entity_id,
            "deduplicate": True,
            "database_url": "",
            "diagnostics": True,
        },
    )
    assert flow["type"] == "create_entry"
    entry = flow["result"]
    await hass.async_block_till_done()
    assert DOMAIN in hass.data
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": DOMAIN + "/get_dashboard", "api_version": 1})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["data"]["summary"]["purchases"] == 0
    duplicate = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert duplicate["type"] == "abort"
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert DOMAIN not in hass.data
