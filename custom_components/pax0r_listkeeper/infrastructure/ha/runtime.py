"""Bounded event scheduling, retry after failures, and clean shutdown."""

import asyncio
import logging
from datetime import UTC, datetime

from ...application.reconcile import ReconcileShoppingList

_LOGGER = logging.getLogger(__name__)


class Runtime:
    def __init__(
        self, hass, uow, adapter, list_id: str, deduplicate: bool, diagnostics: bool = False
    ) -> None:
        self.hass, self.uow, self.adapter = hass, uow, adapter
        self.reconcile = ReconcileShoppingList(uow, adapter, list_id, deduplicate)
        self.gate = asyncio.Lock()
        self.tasks: set[asyncio.Task] = set()
        self.unsubscribers = []
        self.stopping = False
        self.error: str | None = None
        self.last_sync: str | None = None
        self.healthy = False
        self.pending = None
        self.worker = None
        self.retry_task = None
        self.diagnostics = diagnostics

    def changed(self, event) -> None:
        if self.stopping:
            return
        try:
            snapshot = self.adapter.read_now()
        except ValueError:
            snapshot = None
            self.healthy = False
        data = event.data
        item = data.get("item", {})
        added_uid = item.get("id") if data.get("action") == "add" else None
        if self.pending is not None and self.pending[1] == snapshot and added_uid is None:
            added_uid = self.pending[2]
        self.pending = (datetime.now(UTC), snapshot, added_uid)
        if self.worker is None or self.worker.done():
            self.worker = self.hass.async_create_task(self.drain())
            self.tasks.add(self.worker)
            self.worker.add_done_callback(self.tasks.discard)

    async def drain(self) -> None:
        while self.pending is not None and not self.stopping:
            at, captured, added_uid = self.pending
            self.pending = None
            await self.sync(at, captured, added_uid)

    async def sync(self, at=None, captured=None, added_uid=None) -> None:
        async with self.gate:
            if self.stopping:
                return
            try:
                current = await self.adapter.read()
                trusted = self.healthy and captured is not None and captured == current
                observed_at = at if trusted and at is not None else datetime.now(UTC)
                await self.reconcile.execute(observed_at, trusted, added_uid)
                self.healthy = True
                self.error = None
                self.last_sync = datetime.now(UTC).isoformat()
            except Exception:
                # SQL/driver exceptions can contain URLs: never log their text.
                self.healthy = False
                if self.error is None:
                    _LOGGER.error("Synchronization failed; operations are suspended until retry")
                self.error = (
                    "Synchronization suspended. Check the list, database and SQL permissions."
                )
                if not self.stopping and (self.retry_task is None or self.retry_task.done()):
                    self.retry_task = self.hass.async_create_task(self.retry())
                    self.tasks.add(self.retry_task)
                    self.retry_task.add_done_callback(self.tasks.discard)

    async def retry(self) -> None:
        while not self.stopping and self.error:
            await asyncio.sleep(30)
            await self.sync()

    async def close(self) -> None:
        if self.stopping:
            return
        self.stopping = True
        for unsubscribe in self.unsubscribers:
            unsubscribe()
        for task in list(self.tasks):
            task.cancel()
        if self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)
        async with self.gate:
            await self.uow.close()
