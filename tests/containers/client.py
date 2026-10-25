"""Black-box HA client. Errors never include tokens, passwords or response bodies."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

DOMAIN = "pax0r_listkeeper"


class ApiError(RuntimeError):
    def __init__(self, operation: str, code: str) -> None:
        self.code = code
        super().__init__(f"{operation}: {code}")


async def eventually(
    probe: Callable[[], Awaitable[Any]],
    predicate: Callable[[Any], bool],
    description: str,
    wait_seconds: float = 60,
    interval: float = 0.25,
) -> Any:
    try:
        async with asyncio.timeout(wait_seconds):
            while True:
                try:
                    value = await probe()
                    if predicate(value):
                        return value
                except ApiError, aiohttp.ClientError, TimeoutError, OSError:
                    pass  # Expected during startup/reload/restart.
                await asyncio.sleep(interval)
    except TimeoutError:
        raise AssertionError(f"Timed out waiting for {description}") from None


class HaClient:
    def __init__(self, session: aiohttp.ClientSession, base_url: str, token: str = "") -> None:
        self.session, self.base_url, self.token = session, base_url.rstrip("/"), token
        self.entity_id = ""
        self.entry_id = ""

    async def request(
        self,
        method: str,
        path: str,
        *,
        payload=None,
        form=None,
        authenticated: bool = True,
        text: bool = False,
    ):
        headers = {"Authorization": f"Bearer {self.token}"} if authenticated else {}
        async with self.session.request(
            method,
            self.base_url + path,
            json=payload,
            data=form,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=90),
        ) as response:
            if response.status not in {200, 201}:
                raise ApiError(path, f"HTTP {response.status}")
            return await response.text() if text else await response.json()

    async def ws(self, command: str, **fields):
        async with self.session.ws_connect(self.base_url + "/api/websocket") as socket:
            async with asyncio.timeout(90):
                required = await socket.receive_json()
                if required.get("type") != "auth_required":
                    raise ApiError(command, "missing_auth_challenge")
                await socket.send_json({"type": "auth", "access_token": self.token})
                authenticated = await socket.receive_json()
                if authenticated.get("type") != "auth_ok":
                    raise ApiError(command, "authentication_failed")
                await socket.send_json({"id": 1, "type": command, **fields})
                while True:
                    response = await socket.receive_json()
                    if response.get("id") != 1 or response.get("type") != "result":
                        continue
                    if not response.get("success"):
                        raise ApiError(command, response.get("error", {}).get("code", "unknown"))
                    return response.get("result")

    async def app(self, action: str, **fields):
        result = await self.ws(f"{DOMAIN}/{action}", api_version=1, **fields)
        if result.get("api_version") != 1:
            raise ApiError(action, "unsupported_api_version")
        return result["data"]

    async def flow(self, handler: str, data: dict, *, options: bool = False):
        path = "/api/config/config_entries/" + ("options/flow" if options else "flow")
        result = await self.request("POST", path, payload={"handler": handler})
        if result["type"] == "form":
            result = await self.request("POST", f"{path}/{result['flow_id']}", payload=data)
        if result["type"] != "create_entry":
            raise ApiError(
                handler, f"flow_{result['type']}:{result.get('errors', result.get('reason'))}"
            )
        return result

    async def ready(self):
        return await eventually(
            lambda: self.app("get_diagnostics"),
            lambda d: d["last_sync"] is not None and d["error"] is None,
            "healthy Listkeeper",
            wait_seconds=180,
        )

    async def items(self):
        return await self.ws("shopping_list/items")

    async def add(self, name: str) -> str:
        item = await self.ws("shopping_list/items/add", name=name)
        uid = item["id"]
        await eventually(
            lambda: self.app("export_data"),
            lambda d: any(i["uid"] == uid and i["present"] for i in d["data"]["items"].values()),
            "new item snapshot",
        )
        return uid

    async def complete(self, uid: str, completed: bool = True):
        await self.ws("shopping_list/items/update", item_id=uid, complete=completed)

    async def history(self):
        return await self.app("get_purchase_history")

    async def set_deduplication(self, enabled: bool):
        before = (await self.ready())["last_sync"]
        await self.flow(
            self.entry_id,
            {
                "entity_id": self.entity_id,
                "deduplicate": enabled,
                "database_url": "",
                "reset_database_url": False,
                "diagnostics": True,
            },
            options=True,
        )
        await eventually(
            lambda: self.app("get_diagnostics"),
            lambda d: (
                d["deduplicate"] == enabled
                and d["last_sync"] is not None
                and d["last_sync"] != before
                and d["error"] is None
            ),
            "options reload",
        )

    async def token_from_code(self, code: str) -> str:
        result = await self.request(
            "POST",
            "/auth/token",
            authenticated=False,
            form={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.base_url + "/",
            },
        )
        return result["access_token"]

    async def login(self, username: str, password: str) -> str:
        flow = await self.request(
            "POST",
            "/auth/login_flow",
            authenticated=False,
            payload={
                "client_id": self.base_url + "/",
                "redirect_uri": self.base_url + "/",
                "handler": ["homeassistant", None],
            },
        )
        result = await self.request(
            "POST",
            f"/auth/login_flow/{flow['flow_id']}",
            authenticated=False,
            payload={"username": username, "password": password, "client_id": self.base_url + "/"},
        )
        if result["type"] != "create_entry":
            raise ApiError("login", "login_failed")
        return await self.token_from_code(result["result"])
