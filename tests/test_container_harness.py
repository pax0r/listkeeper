"""Test the real client transport against small controlled HTTP/WebSocket fixtures."""

import asyncio
from copy import deepcopy

import pytest

aiohttp = pytest.importorskip("aiohttp")
from aiohttp import web  # noqa: E402

from tests.containers.client import ApiError, HaClient, eventually  # noqa: E402
from tests.containers.isolation import test_instance_url as instance_url  # noqa: E402


@pytest.fixture
async def endpoint():
    tokens, messages = [], []

    async def websocket(request):
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        await socket.send_json({"type": "auth_required"})
        tokens.append(await socket.receive_json())
        await socket.send_json({"type": "auth_ok"})
        message = await socket.receive_json()
        messages.append(message)
        await socket.send_json({"id": 999, "type": "event"})
        if message["type"].endswith("/denied"):
            await socket.send_json(
                {
                    "id": 1,
                    "type": "result",
                    "success": False,
                    "error": {"code": "unauthorized", "message": "secret"},
                }
            )
        else:
            await socket.send_json(
                {
                    "id": 1,
                    "type": "result",
                    "success": True,
                    "result": {"api_version": 1, "data": {"ok": True}},
                }
            )
        await socket.close()
        return socket

    async def private(request):
        return web.json_response({"secret": "never echo errors"}, status=401)

    app = web.Application()
    app.router.add_get("/api/websocket", websocket)
    app.router.add_get("/private", private)
    runner = web.AppRunner(app)
    await runner.setup()
    server = await asyncio.get_running_loop().create_server(runner.server, "127.0.0.1", 0)
    try:
        port = server.sockets[0].getsockname()[1]
        async with aiohttp.ClientSession() as session:
            yield HaClient(session, f"http://127.0.0.1:{port}", "synthetic-token"), tokens, messages
    finally:
        server.close()
        await server.wait_closed()
        await runner.cleanup()


async def test_transport_authenticates_versions_request_and_ignores_other_ids(endpoint):
    client, tokens, messages = endpoint
    assert await client.app("get_dashboard", days=30) == {"ok": True}
    assert tokens == [{"type": "auth", "access_token": "synthetic-token"}]
    assert messages[0] == {
        "id": 1,
        "type": "pax0r_listkeeper/get_dashboard",
        "api_version": 1,
        "days": 30,
    }


async def test_transport_redacts_websocket_and_http_error_bodies(endpoint):
    client, _, _ = endpoint
    with pytest.raises(ApiError) as denied:
        await client.app("denied")
    assert denied.value.code == "unauthorized"
    assert "secret" not in str(denied.value)
    with pytest.raises(ApiError) as private:
        await client.request("GET", "/private")
    assert private.value.code == "HTTP 401"
    assert "never echo" not in str(private.value)


async def test_eventually_retries_transient_failure_and_has_a_deadline():
    calls = 0

    async def transient():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ApiError("startup", "not_loaded")
        return calls

    assert await eventually(transient, lambda value: value == 2, "ready", interval=0) == 2
    with pytest.raises(AssertionError, match="Timed out"):
        await eventually(transient, lambda value: False, "never ready", wait_seconds=0, interval=0)


def inspected_container():
    return {
        "Config": {
            "Labels": {
                "io.pax0r.listkeeper.test-instance": "true",
                "com.docker.compose.project": "listkeeper-test-unit",
                "com.docker.compose.service": "homeassistant",
            }
        },
        "NetworkSettings": {"Ports": {"8123/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8124"}]}},
    }


def test_isolation_accepts_only_owned_loopback_container():
    assert instance_url(inspected_container(), "listkeeper-test-unit") == "http://127.0.0.1:8124"
    with pytest.raises(ValueError, match="not owned"):
        instance_url(inspected_container(), "another-project")


@pytest.mark.parametrize("alteration", ["label", "service", "binding"])
def test_isolation_refuses_unmarked_or_public_container(alteration):
    metadata = deepcopy(inspected_container())
    if alteration == "label":
        metadata["Config"]["Labels"].pop("io.pax0r.listkeeper.test-instance")
    elif alteration == "service":
        metadata["Config"]["Labels"]["com.docker.compose.service"] = "production"
    else:
        metadata["NetworkSettings"]["Ports"]["8123/tcp"][0]["HostIp"] = "0.0.0.0"
    with pytest.raises(ValueError):
        instance_url(metadata, "listkeeper-test-unit")
