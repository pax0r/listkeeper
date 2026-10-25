from datetime import timedelta

import pytest

from custom_components.pax0r_listkeeper.application.catalog import MergeProductNames
from custom_components.pax0r_listkeeper.application.reconcile import ReconcileShoppingList


async def reconcile(memory, shopping, now, **kwargs):
    await ReconcileShoppingList(memory, shopping, "list").execute(now, **kwargs)


@pytest.mark.parametrize(
    "old,new",
    [
        ("Milk", "Milk"),
        ("Milk", "MILK"),
        (" Milk   1l ", "milk 1l"),
    ],
)
@pytest.mark.parametrize("completed", [False, True])
async def test_new_uid_replaces_old_without_purchase(memory, shopping, now, old, new, completed):
    shopping.set("old", old, completed)
    await reconcile(memory, shopping, now)
    shopping.set("new", new)
    await reconcile(memory, shopping, now + timedelta(seconds=1), trusted=True, added_uid="new")
    assert [i.uid for i in shopping.items] == ["new"]
    assert not memory.state.purchases
    await reconcile(memory, shopping, now + timedelta(seconds=2), trusted=True)
    assert shopping.removed == ["old"]


async def test_baseline_duplicates_removed_but_unrelated_names_are_safe(memory, shopping, now):
    shopping.set("a", "Milk")
    shopping.set("b", "Mlik")
    shopping.set("c", "Milk")
    await reconcile(memory, shopping, now)
    assert {i.uid for i in shopping.items} == {"b", "c"}
    assert len(memory.state.products) == 2


async def test_state_notification_before_add_event_preserves_new_uid(memory, shopping, now):
    shopping.set("old", "Milk")
    await reconcile(memory, shopping, now)
    shopping.set("new", "Milk")
    # The generic state event persists an item without reliable addition order.
    await reconcile(memory, shopping, now + timedelta(seconds=1), trusted=True)
    assert [i.uid for i in shopping.items] == ["new"]
    # Its native add event arrives after that transaction has already committed.
    await reconcile(memory, shopping, now + timedelta(seconds=2), trusted=True, added_uid="new")
    assert [i.uid for i in shopping.items] == ["new"]
    assert not memory.state.purchases


async def test_aliases_after_manual_merge(memory, shopping, now):
    shopping.set("a", "Papier WC")
    await reconcile(memory, shopping, now)
    shopping.set("b", "Papier toaletowy")
    await reconcile(memory, shopping, now + timedelta(seconds=1), trusted=True, added_uid="b")
    names = list(memory.state.names)
    await MergeProductNames(memory).execute(names, names[1], now)
    await reconcile(memory, shopping, now)
    assert [i.uid for i in shopping.items] == ["b"]


@pytest.mark.parametrize("minutes,cancelled", [(15, True), (60, True), (61, False)])
async def test_correction_window_and_next_cycle(memory, shopping, now, minutes, cancelled):
    shopping.set("a")
    await reconcile(memory, shopping, now)
    shopping.set("a", completed=True)
    await reconcile(memory, shopping, now, trusted=True)
    await reconcile(memory, shopping, now, trusted=True)
    assert len(memory.state.purchases) == 1
    shopping.set("a", completed=False)
    await reconcile(memory, shopping, now + timedelta(minutes=minutes), trusted=True)
    purchase = next(iter(memory.state.purchases.values()))
    assert (purchase.status == "cancelled") == cancelled
    assert purchase.correction_reason == ("quick_uncheck" if cancelled else None)
    shopping.set("a", completed=True)
    await reconcile(memory, shopping, now + timedelta(minutes=minutes + 1), trusted=True)
    assert len(memory.state.purchases) == 2


async def test_restart_uncheck_never_cancels(memory, shopping, now):
    shopping.set("a")
    await reconcile(memory, shopping, now)
    shopping.set("a", completed=True)
    await reconcile(memory, shopping, now, trusted=True)
    shopping.set("a", completed=False)
    await reconcile(memory, shopping, now + timedelta(minutes=15), trusted=False)
    assert next(iter(memory.state.purchases.values())).status == "confirmed"


async def test_recovery_completion_and_restart_idempotency(memory, shopping, now):
    shopping.set("a")
    await reconcile(memory, shopping, now)
    shopping.set("a", completed=True)
    await reconcile(memory, shopping, now, trusted=False)
    await reconcile(memory, shopping, now, trusted=False)
    assert len(memory.state.purchases) == 1
    assert next(iter(memory.state.purchases.values())).source == "recovery"
    shopping.set("a", completed=False)
    await reconcile(memory, shopping, now + timedelta(minutes=1), trusted=True)
    assert next(iter(memory.state.purchases.values())).status == "confirmed"


async def test_removal_retains_purchase_and_reused_uid_is_new_generation(memory, shopping, now):
    shopping.set("a")
    await reconcile(memory, shopping, now)
    shopping.set("a", completed=True)
    await reconcile(memory, shopping, now, trusted=True)
    shopping.items.clear()
    await reconcile(memory, shopping, now)
    assert len(memory.state.purchases) == 1
    shopping.set("a")
    await reconcile(memory, shopping, now)
    shopping.set("a", completed=True)
    await reconcile(memory, shopping, now, trusted=True)
    assert len(memory.state.purchases) == 2


async def test_bulk_completions(memory, shopping, now):
    for uid in ("a", "b", "c"):
        shopping.set(uid, uid)
    await reconcile(memory, shopping, now)
    for uid in ("a", "b", "c"):
        shopping.set(uid, uid, True)
    await reconcile(memory, shopping, now, trusted=True)
    assert len(memory.state.purchases) == 3


async def test_database_outage_cannot_delete(memory, shopping, now):
    shopping.set("a")
    await reconcile(memory, shopping, now)
    shopping.set("b")
    memory.fail = True
    with pytest.raises(ConnectionError):
        await reconcile(memory, shopping, now, trusted=True, added_uid="b")
    assert len(shopping.items) == 2
    assert not shopping.removed


async def test_failed_delete_and_restart_resume(memory, shopping, now):
    shopping.set("a")
    await reconcile(memory, shopping, now)
    shopping.set("b")
    shopping.fail = True
    with pytest.raises(ConnectionError):
        await reconcile(memory, shopping, now, trusted=True, added_uid="b")
    assert len(memory.state.deduplications) == 1
    shopping.fail = False
    await reconcile(memory, shopping, now)
    assert [i.uid for i in shopping.items] == ["b"]
    assert next(iter(memory.state.deduplications.values())).status == "done"


async def test_multiple_duplicates_converge_and_self_events_do_not_loop(memory, shopping, now):
    for uid in ("a", "b", "c"):
        shopping.set(uid)
    await reconcile(memory, shopping, now)
    shopping.set("new")
    event_count = 0

    def changed():
        nonlocal event_count
        event_count += 1

    shopping.on_remove = changed
    await reconcile(memory, shopping, now, trusted=True, added_uid="new")
    for _ in range(5):
        await reconcile(memory, shopping, now, trusted=True)
    assert [i.uid for i in shopping.items] == ["new"]
    assert event_count == 1
    assert not memory.state.purchases


async def test_pending_delete_invalidated_by_user_change(memory, shopping, now):
    shopping.set("a")
    await reconcile(memory, shopping, now)
    shopping.set("b")
    shopping.fail = True
    with pytest.raises(ConnectionError):
        await reconcile(memory, shopping, now, trusted=True, added_uid="b")
    shopping.set("a", "Different")
    shopping.fail = False
    await reconcile(memory, shopping, now, trusted=True)
    assert len(shopping.items) == 2
    assert next(iter(memory.state.deduplications.values())).status == "superseded"


@pytest.mark.parametrize(
    "statuses", [(True, True, True), (True, False, True), (False, False, False)]
)
async def test_existing_duplicates_collapse_in_one_pass(memory, shopping, now, statuses):
    for uid, completed in zip(("a", "b", "c"), statuses, strict=True):
        shopping.set(uid, "Mydło" if uid == "a" else "MYDLO", completed)
    await reconcile(memory, shopping, now)
    assert len(shopping.items) == 1
    assert shopping.items[0].completed == all(statuses)
    assert len(shopping.removed) == 2
    assert not memory.state.purchases
    await reconcile(memory, shopping, now)
    assert len(shopping.removed) == 2


async def test_existing_accent_variants_join_without_rewriting_history(sql, shopping, now):
    def seed(state):
        from custom_components.pax0r_listkeeper.domain.models import Product, ProductName, Purchase

        for identity, label in (("a", "Mydło"), ("b", "mydlo")):
            state.products[identity] = Product(identity, label)
            state.names[identity] = ProductName(identity, identity, label, label.casefold(), 1, now)
            state.purchases[identity] = Purchase(
                identity, identity, label, "list", identity, now, "confirmed", "live", identity
            )

    await sql.run(seed)
    shopping.set("a", "Mydło", True)
    shopping.set("b", "mydlo", True)
    await ReconcileShoppingList(sql, shopping, "list").execute(now)
    state = await sql.run(lambda state: state)
    assert set(state.names) == {"a", "b"}
    assert len({n.product_id for n in state.names.values()}) == 1
    assert {n.name for n in state.names.values()} == {"Mydło", "mydlo"}
    assert len(state.merges) == 1
    assert set(state.purchases) == {"a", "b"}
    assert {p.original_name for p in state.purchases.values()} == {"Mydło", "mydlo"}
    assert len(shopping.items) == 1
