import asyncio
from types import SimpleNamespace

from custom_components.pax0r_listkeeper.infrastructure.ha.runtime import Runtime


async def test_brief_unavailability_is_not_hidden_by_event_coalescing(memory, shopping, now):
    shopping.read_now = lambda: shopping.items.copy()
    runtime = Runtime(
        SimpleNamespace(async_create_task=asyncio.create_task), memory, shopping, "list", True
    )
    shopping.set("a")
    await runtime.sync()
    shopping.set("a", completed=True)
    await runtime.sync(now, shopping.items.copy())

    def unavailable():
        raise ValueError("unavailable")

    shopping.read_now = unavailable
    runtime.changed(SimpleNamespace(data={}))
    shopping.set("a", completed=False)
    shopping.read_now = lambda: shopping.items.copy()
    runtime.changed(SimpleNamespace(data={}))
    await runtime.worker
    assert next(iter(memory.state.purchases.values())).status == "confirmed"
    await runtime.close()
