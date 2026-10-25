"""HA authentication, strict schemas, portable application DTOs."""

from datetime import UTC, datetime

from homeassistant.components import websocket_api

from ..application.catalog import MergeProductNames, MoveProductName
from ..application.queries import (
    CalendarAnalytics,
    DeleteShoppingData,
    ExportShoppingData,
    GetProductCatalog,
    GetPurchaseHistory,
    GetShoppingStatistics,
)
from ..compat import vol
from ..const import DOMAIN


async def dispatch(hass, runtime, action: str, message: dict):
    uow = runtime.uow
    now = datetime.now(UTC)
    if action == "get_dashboard":
        return await GetShoppingStatistics(
            uow, CalendarAnalytics(hass.config.time_zone, now)
        ).execute(message.get("days"))
    if action in {"get_products", "get_product_names"}:
        names = await GetProductCatalog(uow).execute()
        if action == "get_product_names":
            return names
        return list(
            {
                n["product_id"]: {"id": n["product_id"], "label": n["canonical_name"]}
                for n in names
            }.values()
        )
    if action == "get_purchase_history":
        return await GetPurchaseHistory(uow).execute(
            message.get("name_id"), message.get("offset", 0), message.get("limit", 100)
        )
    if action == "merge_names":
        return await MergeProductNames(uow).execute(
            message["name_ids"], message["target_name_id"], now
        )
    if action == "move_name":
        return await MoveProductName(uow).execute(
            message["name_id"], message.get("product_id"), now
        )
    if action == "export_data":
        return await ExportShoppingData(uow).execute()
    if action == "delete_data":
        await DeleteShoppingData(uow).execute(message["confirmation"])
        # Next reconciliation creates a baseline without touching HA content.
        runtime.healthy = False
        return {"deleted": True}
    if action == "get_diagnostics":
        result = {
            "last_sync": runtime.last_sync,
            "error": runtime.error,
            "deduplicate": runtime.reconcile.deduplicate,
            "entity_id": runtime.adapter.entity_id,
            "database_backend": uow.engine.dialect.name,
            "schema_version": "002",
            "retention": "indefinite",
        }
        if runtime.diagnostics:
            result["operations"] = await uow.run(
                lambda s: {
                    "merge_decisions": len(s.merges),
                    "pending_deletions": sum(
                        o.status == "pending" for o in s.deduplications.values()
                    ),
                }
            )
        return result
    if action == "refresh":
        return {"scheduled": True}
    raise ValueError("Unknown operation")


def make_handler(action: str, fields: dict):
    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/{action}",
            vol.Optional("api_version", default=1): 1,
            **fields,
        }
    )
    @websocket_api.require_admin
    @websocket_api.async_response
    async def handle(hass, connection, message):
        runtime = hass.data.get(DOMAIN)
        if runtime is None or runtime.stopping:
            connection.send_error(message["id"], "not_loaded", "The integration is not loaded")
            return
        try:
            async with runtime.gate:
                if runtime.stopping:
                    connection.send_error(
                        message["id"], "not_loaded", "The integration is not loaded"
                    )
                    return
                result = await dispatch(hass, runtime, action, message)
            if action in {"merge_names", "move_name", "delete_data", "refresh"}:
                await runtime.sync()
            connection.send_result(message["id"], {"api_version": 1, "data": result})
        except ValueError, KeyError:
            connection.send_error(message["id"], "invalid_input", "Invalid input or identifier")
        except Exception:
            connection.send_error(
                message["id"], "storage_error", "The operation failed; check database connectivity"
            )

    return handle


def register_commands(hass) -> None:
    identity = vol.All(str, vol.Length(min=1, max=100))
    commands = {
        "get_dashboard": {vol.Optional("days"): vol.Any(None, 30, 90)},
        "get_products": {},
        "get_product_names": {},
        "get_purchase_history": {
            vol.Optional("name_id"): identity,
            vol.Optional("offset", default=0): vol.All(int, vol.Range(min=0)),
            vol.Optional("limit", default=100): vol.All(int, vol.Range(min=1, max=500)),
        },
        "merge_names": {
            vol.Required("name_ids"): vol.All([identity], vol.Length(min=2, max=500)),
            vol.Required("target_name_id"): identity,
        },
        "move_name": {
            vol.Required("name_id"): identity,
            vol.Optional("product_id"): vol.Any(None, identity),
        },
        "export_data": {},
        "delete_data": {vol.Required("confirmation"): "DELETE SHOPPING HISTORY"},
        "get_diagnostics": {},
        "refresh": {},
    }
    for action, fields in commands.items():
        websocket_api.async_register_command(hass, make_handler(action, fields))
