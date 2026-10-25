"""pax0r's Listkeeper custom integration."""

from .const import DOMAIN


def _config_entry_only_schema(config: dict) -> dict:
    """Use HA's schema helper lazily so domain imports do not require HA."""
    from homeassistant.helpers import config_validation as cv

    return cv.config_entry_only_config_schema(DOMAIN)(config)


CONFIG_SCHEMA = _config_entry_only_schema


async def async_setup(hass, config) -> bool:
    from .api.websocket import register_commands

    register_commands(hass)
    return True


async def async_setup_entry(hass, entry) -> bool:
    from pathlib import Path

    from homeassistant.components import frontend, panel_custom
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.core import callback
    from homeassistant.exceptions import ConfigEntryNotReady
    from homeassistant.helpers.event import async_track_state_change_event

    from .application.scoping import claim_legacy_data
    from .const import ASSET_URL, PANEL_PATH
    from .infrastructure.database.store import SqlUnitOfWork
    from .infrastructure.ha.collection import RuntimeCollection
    from .infrastructure.ha.database_config import database_url
    from .infrastructure.ha.shopping_list import NativeShoppingList

    settings = {**entry.data, **entry.options}
    selected = settings.get("entity_ids", [settings.get("entity_id", "todo.shopping_list")])
    adapters = {entity_id: NativeShoppingList(hass, entity_id) for entity_id in selected}
    uow = None
    try:
        for adapter in adapters.values():
            adapter.entity(require_available=False)
        url = database_url(hass, settings.get("database_url", ""))
        uow = await hass.async_add_executor_job(SqlUnitOfWork, url)
        await hass.async_add_executor_job(uow.initialize)
        legacy = settings.get("legacy_entity_id", settings.get("entity_id"))
        await claim_legacy_data(uow, legacy)
    except Exception:
        if uow:
            await uow.close()
        raise ConfigEntryNotReady(
            "Cannot start the integration. Check selected lists, SQL connection and permissions."
        ) from None
    runtime = RuntimeCollection(
        hass,
        uow,
        adapters,
        settings.get("deduplicate", True),
        settings.get("diagnostics", False),
    )
    entry.runtime_data = runtime
    hass.data[DOMAIN] = runtime
    try:
        if not hass.data.get(DOMAIN + "_assets"):
            await hass.http.async_register_static_paths(
                [StaticPathConfig(ASSET_URL, str(Path(__file__).parent / "frontend"), False)]
            )
            hass.data[DOMAIN + "_assets"] = True
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_PATH,
            webcomponent_name="pax0r-listkeeper-panel",
            sidebar_title="pax0r's Listkeeper",
            sidebar_icon="mdi:cart-outline",
            module_url=ASSET_URL + "/panel.js?v=0.2.0",
            require_admin=True,
        )

        from types import SimpleNamespace

        for entity_id, child in runtime.runtimes.items():

            @callback
            def changed(event, target=child):
                target.changed(event)

            @callback
            def items_changed(_items, target=child):
                target.changed(SimpleNamespace(data={}))

            child.unsubscribers.append(adapters[entity_id].subscribe(items_changed))
            child.unsubscribers.append(async_track_state_change_event(hass, [entity_id], changed))
            from homeassistant.helpers import entity_registry as er

            registered = er.async_get(hass).async_get(entity_id)
            if registered and registered.platform == "shopping_list":
                child.unsubscribers.append(hass.bus.async_listen("shopping_list_updated", changed))

        async def stop(_event):
            await runtime.close()

        # Runtime.close owns unsubscription. A one-time listener would remove
        # itself first, making shutdown cleanup try to unsubscribe it twice.
        runtime.unsubscribers.append(hass.bus.async_listen("homeassistant_stop", stop))
        await runtime.sync()
        runtime.unsubscribers.append(entry.add_update_listener(_updated))
    except Exception:
        await runtime.close()
        hass.data.pop(DOMAIN, None)
        frontend.async_remove_panel(hass, PANEL_PATH)
        raise
    return True


async def _updated(hass, entry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass, entry) -> bool:
    """Preserve ownership of the original catalog when enabling multiple lists."""
    if entry.version > 2:
        return False
    if entry.version == 1:
        settings = {**entry.data, **entry.options}
        original = settings.get("entity_id", "todo.shopping_list")
        data = {**entry.data, "entity_ids": [original], "legacy_entity_id": original}
        options = {**entry.options, "entity_ids": [original]}
        hass.config_entries.async_update_entry(entry, data=data, options=options, version=2)
    return True


async def async_unload_entry(hass, entry) -> bool:
    from homeassistant.components import frontend

    from .const import PANEL_PATH

    await entry.runtime_data.close()
    hass.data.pop(DOMAIN, None)
    frontend.async_remove_panel(hass, PANEL_PATH)
    return True
