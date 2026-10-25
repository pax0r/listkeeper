"""pax0r's Listkeeper custom integration."""

from .const import DOMAIN


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

    from .const import ASSET_URL, PANEL_PATH
    from .infrastructure.database.store import SqlUnitOfWork
    from .infrastructure.ha.database_config import database_url
    from .infrastructure.ha.runtime import Runtime
    from .infrastructure.ha.shopping_list import NativeShoppingList

    settings = {**entry.data, **entry.options}
    adapter = NativeShoppingList(hass, settings["entity_id"])
    uow = None
    try:
        await adapter.read()
        url = database_url(hass, settings.get("database_url", ""))
        uow = await hass.async_add_executor_job(SqlUnitOfWork, url)
        await hass.async_add_executor_job(uow.initialize)
    except Exception:
        if uow:
            await uow.close()
        raise ConfigEntryNotReady(
            "Cannot start the integration. Check the native list, SQL connection and permissions."
        ) from None
    runtime = Runtime(
        hass,
        uow,
        adapter,
        settings["entity_id"],
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
            module_url=ASSET_URL + "/panel.js?v=0.1.0",
            require_admin=True,
        )

        @callback
        def changed(event):
            runtime.changed(event)

        runtime.unsubscribers.extend(
            [
                hass.bus.async_listen("shopping_list_updated", changed),
                async_track_state_change_event(hass, [settings["entity_id"]], changed),
            ]
        )

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


async def async_unload_entry(hass, entry) -> bool:
    from homeassistant.components import frontend

    from .const import PANEL_PATH

    await entry.runtime_data.close()
    hass.data.pop(DOMAIN, None)
    frontend.async_remove_panel(hass, PANEL_PATH)
    return True
