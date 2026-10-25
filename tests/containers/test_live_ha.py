"""Observable behavior through real HA HTTP/WebSocket; no SQL/HA internals."""

import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

pytestmark = [pytest.mark.container, pytest.mark.asyncio(loop_scope="session")]


def helpers():
    # Dependencies are optional outside the explicitly requested container suite.
    from .client import ApiError, HaClient, eventually

    return ApiError, HaClient, eventually


@pytest.mark.parametrize(
    "first,second",
    [
        ("Mleko 3%", "Mleko 3%"),
        ("Mleko 3%", "MLEKO 3%"),
        ("  Papier   WC ", "papier wc"),
    ],
)
async def test_event_deduplication_preserves_new_uid(live_ha, first, second):
    _, _, eventually = helpers()
    client = live_ha.client
    old_uid = await client.add(first)
    new_uid = await client.add(second)
    items = await eventually(client.items, lambda items: len(items) == 1, "deduplication")
    assert items[0]["id"] == new_uid
    assert old_uid != new_uid
    assert (await client.history())["events"] == []
    exported = await client.app("export_data")
    assert any(o["status"] == "done" for o in exported["data"]["deduplications"].values())


async def test_completion_quick_correction_and_recheck(live_ha):
    _, _, eventually = helpers()
    client = live_ha.client
    uid = await client.add("Kawa 250g")
    await client.complete(uid)
    first = await eventually(client.history, lambda h: h["total"] == 1, "purchase")
    event_id = first["events"][0]["id"]
    await client.complete(uid, False)
    corrected = await eventually(
        client.history,
        lambda h: h["events"][0]["status"] == "cancelled",
        "quick uncheck correction",
    )
    assert corrected["events"][0]["correction_reason"] == "quick_uncheck"
    assert corrected["events"][0]["id"] == event_id
    await client.complete(uid)
    await eventually(client.history, lambda h: h["total"] == 2, "next purchase cycle")
    assert (await client.app("get_dashboard"))["summary"]["purchases"] == 1


async def test_completed_duplicate_retains_history(live_ha):
    _, _, eventually = helpers()
    client = live_ha.client
    old_uid = await client.add("Masło")
    await client.complete(old_uid)
    before = await eventually(client.history, lambda h: h["total"] == 1, "confirmed purchase")
    new_uid = await client.add("MASŁO")
    items = await eventually(
        client.items, lambda items: len(items) == 1, "completed duplicate deletion"
    )
    assert items[0]["id"] == new_uid
    assert (await client.history())["events"] == before["events"]


async def test_alias_merge_split_and_future_matching(live_ha):
    _, _, eventually = helpers()
    client = live_ha.client
    first_uid = await client.add("Papier toaletowy")
    await client.complete(first_uid)
    await eventually(client.history, lambda h: h["total"] == 1, "first name purchase")
    second_uid = await client.add("Papier WC")
    await client.complete(second_uid)
    history = await eventually(client.history, lambda h: h["total"] == 2, "second name purchase")
    names = await client.app("get_product_names")
    target = next(n for n in names if n["name"] == "Papier toaletowy")
    other = next(n for n in names if n["name"] == "Papier WC")
    await client.app(
        "merge_names", name_ids=[target["id"], other["id"]], target_name_id=target["id"]
    )
    purchase_days = {
        datetime.fromisoformat(p["occurred_at"]).astimezone(ZoneInfo("Europe/Warsaw")).date()
        for p in history["events"]
    }
    assert (await client.app("get_dashboard"))["summary"]["purchases"] == len(purchase_days)
    assert {p["original_name"] for p in (await client.history())["events"]} == {
        "Papier toaletowy",
        "Papier WC",
    }
    newest = await client.add("Papier WC")
    items = await eventually(client.items, lambda items: len(items) == 1, "alias deduplication")
    assert items[0]["id"] == newest
    await client.app("move_name", name_id=other["id"], product_id=None)
    assert (await client.app("get_dashboard"))["summary"]["purchases"] == 2
    assert {p["id"] for p in (await client.history())["events"]} == {
        p["id"] for p in history["events"]
    }


async def test_unknown_names_rename_and_bulk_completion(live_ha):
    _, _, eventually = helpers()
    client = live_ha.client
    first = await client.add("Mleko 2%")
    await client.add("Mleko 3%")
    assert len(await client.items()) == 2
    await client.ws("shopping_list/items/update", item_id=first, name="Mleko 1,5%")
    await eventually(
        lambda: client.app("get_product_names"),
        lambda names: any(n["name"] == "Mleko 1,5%" for n in names),
        "rename",
    )
    await client.ws("call_service", domain="shopping_list", service="complete_all", service_data={})
    history = await eventually(client.history, lambda h: h["total"] == 2, "bulk completion")
    assert {p["original_name"] for p in history["events"]} == {"Mleko 1,5%", "Mleko 3%"}


async def test_restart_and_reload_preserve_event_ids(live_ha):
    _, _, eventually = helpers()
    client = live_ha.client
    uid = await client.add("Jajka 10 szt.")
    await client.complete(uid)
    before = await eventually(client.history, lambda h: h["total"] == 1, "persisted purchase")
    await live_ha.restart()
    assert (await client.history())["events"] == before["events"]
    await client.request(
        "POST", f"/api/config/config_entries/entry/{client.entry_id}/reload", payload={}
    )
    await client.ready()
    await client.app("refresh")
    assert (await client.history())["events"] == before["events"]
    await client.ws("shopping_list/items/remove", item_id=uid)
    await client.app("refresh")
    assert (await client.history())["events"] == before["events"]


async def test_options_disable_deduplication(live_ha):
    client = live_ha.client
    await client.set_deduplication(False)
    try:
        await client.add("Woda 1l")
        await client.add("WODA 1L")
        await client.app("refresh")
        assert len(await client.items()) == 2
        assert not (await client.app("get_diagnostics"))["deduplicate"]
    finally:
        await client.set_deduplication(True)


async def test_panel_assets_schema_and_single_instance(live_ha):
    client = live_ha.client
    panels = await client.ws("get_panels")
    panel = panels["pax0r-listkeeper"]
    assert panel["require_admin"]
    for filename in ("panel.js", "api.js", "translations.js", "view-model.js"):
        content = await client.request("GET", f"/pax0r_listkeeper_static/{filename}", text=True)
        assert content.strip()
    diagnostics = await client.app("get_diagnostics")
    assert diagnostics["database_backend"] == "sqlite"
    assert diagnostics["schema_version"] == "002"
    duplicate = await client.request(
        "POST", "/api/config/config_entries/flow", payload={"handler": "pax0r_listkeeper"}
    )
    assert duplicate["type"] == "abort"
    assert duplicate["reason"] in {"already_configured", "single_instance_allowed"}


async def test_authorization_and_invalid_mutations(live_ha):
    ApiError, HaClient, _ = helpers()
    client = live_ha.client
    with pytest.raises(ApiError) as invalid:
        await client.app("delete_data", confirmation="wrong")
    assert invalid.value.code == "invalid_format"
    user = await client.ws(
        "config/auth/create", name="Listkeeper test reader", group_ids=["system-users"]
    )
    user_id = user["user"]["id"]
    password, username = secrets.token_urlsafe(32), "reader-" + secrets.token_hex(4)
    try:
        await client.ws(
            "config/auth_provider/homeassistant/create",
            user_id=user_id,
            username=username,
            password=password,
        )
        token = await client.login(username, password)
        reader = HaClient(client.session, client.base_url, token)
        for action, fields in (
            ("get_dashboard", {}),
            ("export_data", {}),
            ("delete_data", {"confirmation": "DELETE SHOPPING HISTORY"}),
        ):
            with pytest.raises(ApiError) as denied:
                await reader.app(action, **fields)
            assert denied.value.code == "unauthorized"
        assert "pax0r-listkeeper" not in await reader.ws("get_panels")
        with pytest.raises(ApiError) as anonymous:
            await client.request("GET", "/api/config", authenticated=False)
        assert anonymous.value.code == "HTTP 401"
    finally:
        await client.ws("config/auth/delete", user_id=user_id)
