"""Refuse arbitrary HA URLs: discover only the Compose-owned test container."""

import asyncio
import json
import os
import secrets
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[2]


async def docker(*arguments: str) -> str:
    process = await asyncio.create_subprocess_exec(
        "docker",
        *arguments,
        cwd=ROOT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(180):
            output, _errors = await process.communicate()
    except TimeoutError, asyncio.CancelledError:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode:
        raise RuntimeError(f"Docker operation failed: {arguments[0]}")
    return output.decode().strip()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def ha_stack():
    if os.getenv("LISTKEEPER_CONTAINER_TEST") != "1":
        pytest.skip("Use python -m tests.containers.run to start isolated HA")
    import aiohttp

    from .client import HaClient, eventually
    from .isolation import test_instance_url

    project = os.environ["LISTKEEPER_COMPOSE_PROJECT"]
    compose = ("compose", "-f", str(ROOT / "compose.ha-test.yml"), "-p", project)
    identity = await docker(*compose, "ps", "--quiet", "homeassistant")
    metadata = json.loads(await docker("inspect", identity))[0]
    base_url = test_instance_url(metadata, project)
    async with aiohttp.ClientSession() as session:
        client = HaClient(session, base_url)
        onboarding = await client.request("GET", "/api/onboarding", authenticated=False)
        if any(step["step"] == "user" and step["done"] for step in onboarding):
            pytest.fail("Expected a fresh test volume; refusing an already configured HA")
        owner = await client.request(
            "POST",
            "/api/onboarding/users",
            authenticated=False,
            payload={
                "name": "Listkeeper test owner",
                "username": "listkeeper-owner",
                "password": secrets.token_urlsafe(32),
                "language": "en",
                "client_id": base_url + "/",
            },
        )
        client.token = await client.token_from_code(owner["auth_code"])
        # Deliberately skip core_config onboarding: it auto-creates cloud integrations.
        await client.flow("shopping_list", {})
        states = await eventually(
            lambda: client.ws("get_states"),
            lambda values: any(s["entity_id"].startswith("todo.") for s in values),
            "native Shopping List entity",
        )
        client.entity_id = next(
            s["entity_id"] for s in states if s["entity_id"].startswith("todo.")
        )
        result = await client.flow(
            "pax0r_listkeeper",
            {
                "entity_id": client.entity_id,
                "deduplicate": True,
                "database_url": "",
                "reset_database_url": False,
                "diagnostics": True,
            },
        )
        client.entry_id = result["result"]["entry_id"]
        await client.ready()
        configuration = await client.request("GET", "/api/config")
        results = ROOT / "test-results" / project
        results.mkdir(parents=True, exist_ok=True)
        (results / "ha-version.json").write_text(
            json.dumps(
                {
                    "version": configuration["version"],
                    "entity_id": client.entity_id,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        async def restart():
            await docker(*compose, "restart", "--timeout", "90", "homeassistant")
            await client.ready()

        yield SimpleNamespace(client=client, restart=restart)


@pytest_asyncio.fixture(loop_scope="session")
async def live_ha(ha_stack):
    client = ha_stack.client
    await client.ready()
    for item in await client.items():
        await client.ws("shopping_list/items/remove", item_id=item["id"])
    await client.app("refresh")
    await client.app("delete_data", confirmation="DELETE SHOPPING HISTORY")
    assert not (await client.history())["events"]
    yield ha_stack
