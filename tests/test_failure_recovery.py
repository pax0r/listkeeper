"""Durable side effects and identity changes across partial failures."""

from datetime import timedelta

import pytest

from custom_components.pax0r_listkeeper.application.catalog import (
    MergeProductNames,
    MoveProductName,
)
from custom_components.pax0r_listkeeper.application.reconcile import ReconcileShoppingList


async def test_split_invalidates_already_persisted_delete(memory, shopping, now):
    reconcile = ReconcileShoppingList(memory, shopping, "list")
    shopping.set("a", "WC")
    await reconcile.execute(now)
    shopping.set("b", "Papier")
    await reconcile.execute(now + timedelta(seconds=1), trusted=True, added_uid="b")
    names = list(memory.state.names)
    await MergeProductNames(memory).execute(names, names[0], now)
    shopping.fail = True
    with pytest.raises(ConnectionError):
        await reconcile.execute(now)
    await MoveProductName(memory).execute(names[1], None, now)
    shopping.fail = False
    await reconcile.execute(now)
    assert {i.uid for i in shopping.items} == {"a", "b"}
    assert all(o.status == "superseded" for o in memory.state.deduplications.values())


async def test_crash_after_external_delete_before_sql_ack(memory, shopping, now):
    reconcile = ReconcileShoppingList(memory, shopping, "list")
    shopping.set("a")
    await reconcile.execute(now)
    shopping.set("b")
    shopping.on_remove = lambda: setattr(memory, "fail", True)
    with pytest.raises(ConnectionError):
        await reconcile.execute(now + timedelta(seconds=1), trusted=True, added_uid="b")
    assert [i.uid for i in shopping.items] == ["b"]
    assert next(iter(memory.state.deduplications.values())).status == "pending"
    memory.fail = False
    shopping.on_remove = None
    await ReconcileShoppingList(memory, shopping, "list").execute(now)
    assert shopping.removed == ["a"]
    assert next(iter(memory.state.deduplications.values())).status == "done"


async def test_completed_batch_resumes_after_first_delete_before_ack(memory, shopping, now):
    for uid in ("a", "b", "c", "d"):
        shopping.set(uid, "Soap", True)
    shopping.on_remove = lambda: setattr(memory, "fail", True)
    with pytest.raises(ConnectionError):
        await ReconcileShoppingList(memory, shopping, "list").execute(now)
    assert len(shopping.items) == 3
    memory.fail = False
    shopping.on_remove = None
    await ReconcileShoppingList(memory, shopping, "list").execute(now)
    assert [i.uid for i in shopping.items] == ["d"]
    assert len(shopping.removed) == 3
    assert all(o.status == "done" for o in memory.state.deduplications.values())
    assert not memory.state.purchases


async def test_completed_duplicate_purchase_survives_removal(memory, shopping, now):
    reconcile = ReconcileShoppingList(memory, shopping, "list")
    shopping.set("a")
    await reconcile.execute(now)
    shopping.set("a", completed=True)
    await reconcile.execute(now, trusted=True)
    shopping.set("b")
    await reconcile.execute(now + timedelta(seconds=1), trusted=True, added_uid="b")
    await reconcile.execute(now + timedelta(seconds=2), trusted=True)
    assert [i.uid for i in shopping.items] == ["b"]
    assert len(memory.state.purchases) == 1
    assert next(iter(memory.state.purchases.values())).status == "confirmed"


async def test_deduplication_disabled_preserves_list_and_records_purchases(memory, shopping, now):
    reconcile = ReconcileShoppingList(memory, shopping, "list", deduplicate=False)
    shopping.set("a")
    await reconcile.execute(now)
    shopping.set("b")
    await reconcile.execute(now, trusted=True, added_uid="b")
    shopping.set("a", completed=True)
    await reconcile.execute(now, trusted=True)
    assert len(shopping.items) == 2
    assert len(memory.state.purchases) == 1
    assert not memory.state.deduplications
