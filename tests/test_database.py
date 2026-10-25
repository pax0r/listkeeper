import asyncio
import os
from dataclasses import replace

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from custom_components.pax0r_listkeeper.application.catalog import MergeProductNames
from custom_components.pax0r_listkeeper.application.queries import DeleteShoppingData
from custom_components.pax0r_listkeeper.application.reconcile import (
    ReconcileShoppingList,
    observe_name,
)
from custom_components.pax0r_listkeeper.domain.models import new_id
from custom_components.pax0r_listkeeper.infrastructure.database.migrations import upgrade
from custom_components.pax0r_listkeeper.infrastructure.database.store import SqlUnitOfWork


async def test_sql_roundtrip_idempotency_and_restart(sql, shopping, now):
    shopping.set("a")
    await ReconcileShoppingList(sql, shopping, "list").execute(now)
    shopping.set("a", completed=True)
    await ReconcileShoppingList(sql, shopping, "list").execute(now, trusted=True)
    await ReconcileShoppingList(sql, shopping, "list").execute(now)
    result = await sql.run(lambda s: list(s.purchases.values()))
    assert len(result) == 1
    assert result[0].occurred_at == now
    assert result[0].original_name == "Milk"


async def test_sql_foreign_keys_rollback_and_erase(sql, now):
    def seed(s):
        observe_name(s, "A", now)
        observe_name(s, "B", now)

    await sql.run(seed)
    names = await sql.run(lambda s: list(s.names))
    await MergeProductNames(sql).execute(names, names[0], now)

    def fail(s):
        s.names[names[0]].product_id = "missing"

    with pytest.raises(IntegrityError):
        await sql.run(fail)
    assert await sql.run(lambda s: len(s.names)) == 2
    await DeleteShoppingData(sql).execute("DELETE SHOPPING HISTORY")
    assert await sql.run(lambda s: len(s.names)) == 0


async def test_concurrent_sql_transactions(sql, now):
    await asyncio.gather(*(sql.run(lambda s: observe_name(s, "Same", now)) for _ in range(8)))
    assert await sql.run(lambda s: len(s.names)) == 1


def test_upgrade_from_v1_and_repeat_without_data_loss(tmp_path):
    store = SqlUnitOfWork("sqlite:///" + str(tmp_path / "migration.db"))
    upgrade(store.engine, "001")
    with store.engine.begin() as connection:
        connection.execute(
            text("INSERT INTO pax0r_listkeeper_products (id, label) VALUES ('p', 'A')")
        )
    store.initialize()
    store.initialize()
    with store.engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT label FROM pax0r_listkeeper_products WHERE id='p'"))
            == "A"
        )
        assert (
            connection.scalar(text("SELECT version_num FROM pax0r_listkeeper_alembic_version"))
            == "002"
        )
        indexes = inspect(connection).get_indexes("pax0r_listkeeper_purchase_events")
        assert any(i["column_names"] == ["name_id", "occurred_at"] for i in indexes)
    store.engine.dispose()


async def test_normalized_name_unique_constraint(sql, now):
    await sql.run(lambda s: observe_name(s, "Milk", now))

    def duplicate(state):
        original = next(iter(state.names.values()))
        copied = replace(original, id=new_id())
        state.names[copied.id] = copied

    with pytest.raises(IntegrityError):
        await sql.run(duplicate)
    assert await sql.run(lambda s: len(s.names)) == 1


@pytest.mark.skipif(not os.getenv("SI_TEST_DATABASE_URL"), reason="Requires isolated SQL container")
async def test_server_database_full_roundtrip(shopping, now):
    store = SqlUnitOfWork(os.environ["SI_TEST_DATABASE_URL"])
    upgrade(store.engine, "001")
    store.initialize()
    try:
        await test_sql_roundtrip_idempotency_and_restart(store, shopping, now)
        await DeleteShoppingData(store).execute("DELETE SHOPPING HISTORY")
        await test_sql_foreign_keys_rollback_and_erase(store, now)
        store.initialize()
        with store.engine.connect() as connection:
            if store.engine.dialect.name == "postgresql":
                assert connection.scalar(text("SELECT current_schema()")) == "pax0r_listkeeper"
    finally:
        await store.close()
