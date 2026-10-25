"""Independent catalogs, histories and mutations using the same SQL database."""

import asyncio

import pytest

from custom_components.pax0r_listkeeper.application.catalog import (
    MergeProductNames,
    MoveProductName,
)
from custom_components.pax0r_listkeeper.application.queries import (
    DeleteShoppingData,
    ExportShoppingData,
)
from custom_components.pax0r_listkeeper.application.reconcile import ReconcileShoppingList
from custom_components.pax0r_listkeeper.application.scoping import ListUnitOfWork, claim_legacy_data
from tests.conftest import FakeList


async def seed(uow, list_id, now):
    shopping = FakeList()
    shopping.set("same-uid", "Soap")
    reconcile = ReconcileShoppingList(uow, shopping, list_id)
    await reconcile.execute(now)
    shopping.set("same-uid", "Soap", True)
    await reconcile.execute(now, trusted=True)
    return shopping


async def test_same_names_and_uids_are_independent_and_erase_is_scoped(sql, now):
    first, second = ListUnitOfWork(sql, "todo.home"), ListUnitOfWork(sql, "todo.test")
    await asyncio.gather(seed(first, "todo.home", now), seed(second, "todo.test", now))
    a, b = await first.run(lambda s: s), await second.run(lambda s: s)
    assert set(a.names).isdisjoint(b.names)
    assert set(a.products).isdisjoint(b.products)
    assert len(a.purchases) == len(b.purchases) == 1
    exported = await ExportShoppingData(first).execute()
    assert set(exported["data"]["purchases"]) == set(a.purchases)
    await DeleteShoppingData(first).execute("DELETE SHOPPING HISTORY")
    assert not await first.run(lambda s: s.names)
    assert await second.run(lambda s: s) == b
    assert await second.run(lambda s: s.initialized_lists) == {"todo.test"}


async def test_foreign_name_and_product_ids_cannot_be_moved_or_merged(sql, now):
    first, second = ListUnitOfWork(sql, "todo.home"), ListUnitOfWork(sql, "todo.test")
    await seed(first, "todo.home", now)
    await seed(second, "todo.test", now)
    a, b = await first.run(lambda s: s), await second.run(lambda s: s)
    with pytest.raises(KeyError):
        await MoveProductName(first).execute(next(iter(a.names)), next(iter(b.products)), now)
    with pytest.raises(KeyError):
        await MergeProductNames(first).execute([*a.names, *b.names], next(iter(a.names)), now)
    assert await first.run(lambda s: s) == a
    assert await second.run(lambda s: s) == b


async def test_renaming_is_independent_and_rejects_a_foreign_product(sql, now):
    from custom_components.pax0r_listkeeper.application.catalog import RenameProduct

    first, second = ListUnitOfWork(sql, "todo.home"), ListUnitOfWork(sql, "todo.test")
    await seed(first, "todo.home", now)
    await seed(second, "todo.test", now)
    first_id = await first.run(lambda s: next(iter(s.products)))
    second_id = await second.run(lambda s: next(iter(s.products)))
    await RenameProduct(first).execute(first_id, "Liquid soap", now)
    assert await second.run(lambda s: s.products[second_id].label) == "Soap"
    await RenameProduct(second).execute(second_id, "Liquid soap", now)
    with pytest.raises(KeyError):
        await RenameProduct(first).execute(second_id, "Changed", now)


async def test_normalization_and_deduplication_do_not_cross_lists(sql, now):
    first, second = ListUnitOfWork(sql, "todo.home"), ListUnitOfWork(sql, "todo.test")
    home, testing = await seed(first, "todo.home", now), await seed(second, "todo.test", now)
    original = await second.run(lambda s: s)
    home.set("new", "SOAP")
    await ReconcileShoppingList(first, home, "todo.home").execute(
        now, trusted=True, added_uid="new"
    )
    assert [i.uid for i in home.items] == ["new"]
    assert len(testing.items) == 1
    assert await second.run(lambda s: s) == original


async def test_legacy_claim_is_repeatable_and_preserves_name_and_purchase_ids(sql, now):
    await seed(sql, "todo.home", now)
    before = await sql.run(lambda s: s)
    await claim_legacy_data(sql, "todo.home")
    await claim_legacy_data(sql, "todo.test")
    home, testing = ListUnitOfWork(sql, "todo.home"), ListUnitOfWork(sql, "todo.test")
    migrated = await home.run(lambda s: s)
    assert migrated.names == before.names
    assert migrated.purchases == before.purchases
    assert {p.scope for p in migrated.products.values()} == {"todo.home"}
    assert not await testing.run(lambda s: s.names)


async def test_legacy_shared_catalog_retains_events_and_separates_future_snapshots(sql, now):
    await seed(sql, "todo.home", now)
    await seed(sql, "todo.previous", now)
    purchases = await sql.run(lambda s: s.purchases)
    await claim_legacy_data(sql, "todo.home")
    home, previous = ListUnitOfWork(sql, "todo.home"), ListUnitOfWork(sql, "todo.previous")
    assert await home.run(lambda s: s.purchases) == purchases
    assert not await previous.run(lambda s: s.purchases)
    assert set(await home.run(lambda s: s.names)).isdisjoint(await previous.run(lambda s: s.names))
    shopping = FakeList()
    shopping.set("same-uid", "Soap", True)
    await ReconcileShoppingList(previous, shopping, "todo.previous").execute(now)
    assert await sql.run(lambda s: s.purchases) == purchases


async def test_config_entry_migration_preserves_original_opt_in():
    from types import SimpleNamespace

    from custom_components.pax0r_listkeeper import async_migrate_entry

    entry = SimpleNamespace(
        version=1,
        data={"entity_id": "todo.old"},
        options={"entity_id": "todo.current", "deduplicate": False},
    )

    def update(target, **changes):
        target.__dict__.update(changes)

    hass = SimpleNamespace(config_entries=SimpleNamespace(async_update_entry=update))
    assert await async_migrate_entry(hass, entry)
    assert entry.version == 2
    assert entry.data["legacy_entity_id"] == "todo.current"
    assert entry.options["entity_ids"] == ["todo.current"]
    assert entry.options["deduplicate"] is False
