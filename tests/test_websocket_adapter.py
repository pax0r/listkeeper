"""Verify callback/async decoration against the HA WebSocket scheduling contract."""

import asyncio
import importlib.util
import sys
from functools import wraps
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def ws_handler(monkeypatch):
    tasks = []

    def async_response(function):
        @wraps(function)
        def schedule(*arguments):
            tasks.append(asyncio.create_task(function(*arguments)))

        return schedule

    def require_admin(function):
        @wraps(function)
        def authorize(hass, connection, message):
            if not connection.user.is_admin:
                raise PermissionError("unauthorized")
            function(hass, connection, message)

        return authorize

    websocket_api = SimpleNamespace(
        websocket_command=lambda schema: lambda function: function,
        async_response=async_response,
        require_admin=require_admin,
    )
    components = ModuleType("homeassistant.components")
    components.websocket_api = websocket_api
    monkeypatch.setitem(sys.modules, "homeassistant", ModuleType("homeassistant"))
    monkeypatch.setitem(sys.modules, "homeassistant.components", components)
    compat = ModuleType("custom_components.pax0r_listkeeper.compat")
    compat.vol = SimpleNamespace(Required=lambda key: key, Optional=lambda key, **kwargs: key)
    monkeypatch.setitem(sys.modules, compat.__name__, compat)
    name = "custom_components.pax0r_listkeeper.api.websocket"
    path = Path(__file__).parents[1] / "custom_components/pax0r_listkeeper/api/websocket.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    calls = []

    async def dispatch(hass, runtime, action, message):
        calls.append(action)
        return {"ok": True}

    monkeypatch.setattr(module, "dispatch", dispatch)
    return module.make_handler("get_dashboard", {}), tasks, calls


async def test_admin_callback_schedules_and_awaits_application_handler(ws_handler):
    handler, tasks, calls = ws_handler
    results = []
    connection = SimpleNamespace(
        user=SimpleNamespace(is_admin=True),
        send_result=lambda identity, result: results.append((identity, result)),
    )
    runtime = SimpleNamespace(stopping=False, gate=asyncio.Lock())
    hass = SimpleNamespace(data={"pax0r_listkeeper": runtime})
    assert handler(hass, connection, {"id": 1}) is None
    await asyncio.gather(*tasks)
    assert calls == ["get_dashboard"]
    assert results == [(1, {"api_version": 1, "data": {"ok": True}})]


async def test_nonadmin_rejected_before_scheduling_any_work(ws_handler):
    handler, tasks, calls = ws_handler
    connection = SimpleNamespace(user=SimpleNamespace(is_admin=False))
    with pytest.raises(PermissionError):
        handler(SimpleNamespace(data={}), connection, {"id": 1})
    assert not tasks
    assert not calls
