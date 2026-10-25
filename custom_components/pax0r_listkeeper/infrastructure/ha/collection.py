"""Own opted-in list runtimes and their shared database lifecycle."""

import asyncio

from ...application.scoping import ListUnitOfWork
from .runtime import Runtime


class RuntimeCollection:
    def __init__(self, hass, uow, adapters: dict, deduplicate: bool, diagnostics: bool):
        self.hass, self.uow = hass, uow
        self.runtimes = {
            entity_id: Runtime(
                hass, ListUnitOfWork(uow, entity_id), adapter, entity_id, deduplicate, diagnostics
            )
            for entity_id, adapter in adapters.items()
        }
        self.stopping = False
        for runtime in self.runtimes.values():
            runtime.database_backend = uow.engine.dialect.name
        self.unsubscribers = []

    def select(self, entity_id: str | None):
        if entity_id is None:
            if len(self.runtimes) != 1:
                raise ValueError("Select a list explicitly")
            return next(iter(self.runtimes.values()))
        return self.runtimes[entity_id]

    def lists(self):
        result = []
        for entity_id, runtime in self.runtimes.items():
            state = self.hass.states.get(entity_id)
            result.append(
                {
                    "entity_id": entity_id,
                    "name": state.name if state else entity_id,
                    "error": runtime.error,
                }
            )
        return result

    async def sync(self):
        await asyncio.gather(*(r.sync() for r in self.runtimes.values()))

    async def close(self):
        if self.stopping:
            return
        self.stopping = True
        for unsubscribe in self.unsubscribers:
            unsubscribe()
        await asyncio.gather(*(r.close() for r in self.runtimes.values()))
        await self.uow.close()
