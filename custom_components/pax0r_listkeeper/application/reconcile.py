"""Serialized snapshot reconciliation and durable deletion intents."""

import asyncio
from collections import defaultdict
from datetime import datetime

from ..domain.matching import CompositeMatcher, DuplicateResolver, normalize
from ..domain.models import ListItem, Operation, Product, ProductName, Snapshot, State, new_id
from .history import CorrectPurchase, RecordPurchase
from .ports import ShoppingList, UnitOfWork


def observe_name(state: State, name: str, at: datetime) -> ProductName:
    normalized = normalize(name)
    if not normalized or len(normalized) > 500:
        raise ValueError("Names must contain between 1 and 500 characters")
    found = next((n for n in state.names.values() if n.normalized == normalized), None)
    if found:
        return found
    product = Product(new_id(), name)
    state.products[product.id] = product
    found = ProductName(new_id(), product.id, name, normalized, 0, at)
    state.names[found.id] = found
    return found


class DeduplicationService:
    def __init__(self, uow: UnitOfWork, shopping_list: ShoppingList) -> None:
        self.uow = uow
        self.shopping_list = shopping_list

    async def execute(self, operation: Operation) -> None:
        payload = operation.payload
        expected = [ListItem(**i) for i in payload["expected"]]
        current = await self.shopping_list.read()
        victim, keeper = ListItem(**payload["victim"]), ListItem(**payload["keeper"])

        def authorize(state: State) -> bool:
            names = list(state.names.values())
            matcher = CompositeMatcher()
            victim_match = matcher.match(victim.name, names)
            keeper_match = matcher.match(keeper.name, names)
            return (
                victim_match.product_id is not None
                and victim_match.product_id == keeper_match.product_id
            )

        if not any(i.uid == victim.uid for i in current):
            status = "done"  # Includes crash after removal, before acknowledgement.
        elif sorted(current, key=lambda i: i.uid) != sorted(
            expected, key=lambda i: i.uid
        ) or not await self.uow.run(authorize):
            status = "superseded"
        else:
            removed = await self.shopping_list.remove_if_unchanged(victim, keeper, expected)
            status = "done" if removed else "superseded"

        def acknowledge(state: State) -> None:
            state.deduplications[operation.id].status = status

        await self.uow.run(acknowledge)


class ReconcileShoppingList:
    def __init__(
        self, uow: UnitOfWork, shopping_list: ShoppingList, list_id: str, deduplicate: bool = True
    ) -> None:
        self.uow, self.shopping_list, self.list_id = uow, shopping_list, list_id
        self.deduplicate = deduplicate
        self.lock = asyncio.Lock()
        self.matcher = CompositeMatcher()
        self.resolver = DuplicateResolver()

    async def execute(
        self, at: datetime, trusted: bool = False, added_uid: str | None = None
    ) -> None:
        async with self.lock:
            current = await self.shopping_list.read()
            if len({i.uid for i in current}) != len(current):
                raise ValueError("The list contains duplicate UIDs")

            def reconcile(state: State) -> list[Operation]:
                baseline = self.list_id not in state.initialized_lists
                known = {i.uid: i for i in state.items.values() if i.list_id == self.list_id}
                present = {i.uid for i in current}
                for old in known.values():
                    if old.uid not in present:
                        old.present = False
                for item in current:
                    name = observe_name(state, item.name, at)
                    old = known.get(item.uid)
                    fresh = old is None or not old.present
                    renamed = old is not None and old.name_id != name.id
                    if fresh or renamed:
                        name.occurrences += 1
                        name.last_seen = at
                    if fresh:
                        state.sequence += 1
                        order = state.sequence if trusted and added_uid == item.uid else None
                        if old is None:
                            old = Snapshot(
                                new_id(),
                                self.list_id,
                                item.uid,
                                name.id,
                                item.name,
                                item.completed,
                                True,
                                0,
                                0,
                                at,
                                order,
                            )
                            state.items[old.id] = old
                        else:
                            old.generation += 1
                            old.cycle = 0
                            old.first_seen, old.added_order = at, order
                        # Newly discovered completed items have no observed transition.
                    elif old.completed != item.completed and not baseline:
                        if item.completed:
                            old.name_id, old.name = name.id, item.name
                            RecordPurchase().execute(
                                state, old, at, "live" if trusted else "recovery"
                            )
                        else:
                            CorrectPurchase().execute(state, old, at, trusted)
                    # HA may deliver its state-change notification before the
                    # corresponding add event. Promote that already persisted
                    # snapshot when the reliable UID-specific event arrives.
                    if trusted and added_uid == item.uid and old.added_order is None:
                        state.sequence += 1
                        old.added_order = state.sequence
                    old.name_id, old.name = name.id, item.name
                    old.completed, old.present = item.completed, True
                state.initialized_lists.add(self.list_id)
                if not self.deduplicate:
                    return []
                # Revalidate pending intents after saving all observed purchases.
                pending = [
                    o
                    for o in state.deduplications.values()
                    if o.status == "pending" and o.payload["list_id"] == self.list_id
                ]
                groups = defaultdict(list)
                for item in state.items.values():
                    if item.list_id == self.list_id and item.present:
                        match = self.matcher.match(item.name, list(state.names.values()))
                        if match.product_id:
                            groups[match.product_id].append(item)
                from dataclasses import asdict

                expected = [asdict(i) for i in current]
                for group in groups.values():
                    resolved = self.resolver.resolve(group)
                    if not resolved:
                        continue
                    keeper, victims = resolved
                    for victim in victims:
                        if any(o.payload["victim"]["uid"] == victim.uid for o in pending):
                            continue
                        operation = Operation(
                            new_id(),
                            "deduplicate",
                            at,
                            {
                                "list_id": self.list_id,
                                "victim": asdict(
                                    ListItem(victim.uid, victim.name, victim.completed)
                                ),
                                "keeper": asdict(
                                    ListItem(keeper.uid, keeper.name, keeper.completed)
                                ),
                                "expected": expected,
                                "basis": (
                                    "normalized_exact"
                                    if normalize(victim.name) == normalize(keeper.name)
                                    else "approved_alias"
                                ),
                            },
                        )
                        state.deduplications[operation.id] = operation
                        pending.append(operation)
                return pending

            operations = await self.uow.run(reconcile)
            service = DeduplicationService(self.uow, self.shopping_list)
            for operation in operations:
                await service.execute(operation)
