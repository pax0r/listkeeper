"""Worker-backed SQL Unit of Work; all SQL stays outside the HA event loop."""

import asyncio
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from typing import TypeVar

from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from ...domain.models import Operation, Product, ProductName, Purchase, Snapshot, State
from .migrations import upgrade
from .models import ControlRow, DedupRow, ItemRow, MergeRow, NameRow, ProductRow, PurchaseRow

T = TypeVar("T")
TABLES = (
    ("products", ProductRow, Product),
    ("names", NameRow, ProductName),
    ("items", ItemRow, Snapshot),
    ("purchases", PurchaseRow, Purchase),
    ("merges", MergeRow, Operation),
    ("deduplications", DedupRow, Operation),
)
DATES = {"last_seen", "first_seen", "occurred_at", "corrected_at"}


class SqlUnitOfWork:
    def __init__(self, url: str) -> None:
        parsed = make_url(url)
        if parsed.get_backend_name() not in {"sqlite", "postgresql", "mysql", "mariadb"}:
            raise ValueError("Unsupported SQL backend")
        self.engine = create_engine(parsed, pool_pre_ping=True, hide_parameters=True)
        if parsed.get_backend_name() == "postgresql":

            @event.listens_for(self.engine, "connect")
            def configure_postgresql(connection, _record):
                with connection.cursor() as cursor:
                    cursor.execute("SET search_path TO pax0r_listkeeper")
                connection.commit()

        if parsed.get_backend_name() == "sqlite":

            @event.listens_for(self.engine, "connect")
            def configure_sqlite(connection, _record):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA busy_timeout=10000")

        self.lock = asyncio.Lock()

    def initialize(self) -> None:
        try:
            upgrade(self.engine)
        except Exception:
            self.engine.dispose()
            raise

    def _run(self, work: Callable[[State], T]) -> T:
        with Session(self.engine) as session, session.begin():
            control = session.scalar(select(ControlRow).where(ControlRow.id == 1).with_for_update())
            if control is None:
                raise RuntimeError("The database schema has not been initialized")
            state = State(
                initialized_lists=set(control.initialized_lists), sequence=control.sequence
            )
            rows = {}
            for attribute, model, record in TABLES:
                rows[attribute] = {r.id: r for r in session.scalars(select(model))}
                for row in rows[attribute].values():
                    data = {k: getattr(row, k) for k in record.__dataclass_fields__}
                    for key in DATES & data.keys():
                        if data[key] is not None:
                            data[key] = datetime.fromisoformat(data[key]).astimezone(UTC)
                    getattr(state, attribute)[row.id] = record(**data)
            result = work(state)
            # Explicit deletes support the separately confirmed erase use case.
            for attribute, model, _ in reversed(TABLES):
                removed = set(rows[attribute]) - set(getattr(state, attribute))
                if removed:
                    session.execute(delete(model).where(model.id.in_(removed)))
            for attribute, model, _ in TABLES:
                for identity, record in getattr(state, attribute).items():
                    data = asdict(record)
                    for key in DATES & data.keys():
                        if data[key] is not None:
                            if data[key].tzinfo is None:
                                raise ValueError("A timezone-aware timestamp is required")
                            data[key] = data[key].astimezone(UTC).isoformat()
                    if model is NameRow:
                        data["normalized_hash"] = sha256(data["normalized"].encode()).hexdigest()
                    row = rows[attribute].get(identity)
                    if row is None:
                        session.add(model(**data))
                    else:
                        for key, value in data.items():
                            if getattr(row, key) != value:
                                setattr(row, key, value)
                session.flush()
            control.sequence = state.sequence
            control.initialized_lists = sorted(state.initialized_lists)
            return result

    async def run(self, work: Callable[[State], T]) -> T:
        async with self.lock:
            # Wait for the worker on cancellation: never dispose an in-use engine.
            task = asyncio.create_task(asyncio.to_thread(self._run, work))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                raise

    async def close(self) -> None:
        async with self.lock:
            await asyncio.to_thread(self.engine.dispose)
