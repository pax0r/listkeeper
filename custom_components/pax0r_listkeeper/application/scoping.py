"""Transactionally isolated list views over a shared Unit of Work."""

from collections.abc import Callable
from dataclasses import replace
from typing import TypeVar

from ..domain.models import Product, State, new_id
from .ports import UnitOfWork

T = TypeVar("T")


async def claim_legacy_data(uow: UnitOfWork, list_id: str | None) -> None:
    """Assign the previous single catalog once, without changing identifiers."""

    def claim(state: State) -> None:
        target = list_id
        if target is None and len(state.initialized_lists) == 1:
            target = next(iter(state.initialized_lists))
        legacy_products = {p.id for p in state.products.values() if not p.scope}
        if not legacy_products:
            return
        if target is None:
            raise ValueError("The legacy catalog needs an explicit original list")
        legacy_names = {n.id for n in state.names.values() if n.product_id in legacy_products}
        for product in state.products.values():
            if not product.scope:
                product.scope = target
        for operation in state.merges.values():
            operation.payload.setdefault("list_id", target)
        # Older releases shared a catalog even after changing the selected list.
        # Retain that historical catalog under its original configured context,
        # and give snapshots from other lists independent future name identities.
        copies = {}
        products = {}
        for item in state.items.values():
            if item.list_id == target or item.name_id not in legacy_names:
                continue
            original = state.names[item.name_id]
            key = (item.list_id, original.id)
            if key not in copies:
                product_key = (item.list_id, original.product_id)
                if product_key not in products:
                    product = Product(
                        new_id(), state.products[original.product_id].label, item.list_id
                    )
                    state.products[product.id] = product
                    products[product_key] = product.id
                copied = replace(
                    original,
                    id=new_id(),
                    product_id=products[product_key],
                    occurrences=0,
                    last_seen=item.first_seen,
                )
                state.names[copied.id] = copied
                copies[key] = copied.id
            item.name_id = copies[key]
            state.names[item.name_id].occurrences += 1
            state.names[item.name_id].last_seen = max(
                state.names[item.name_id].last_seen, item.first_seen
            )

    await uow.run(claim)


class ListUnitOfWork:
    def __init__(self, parent: UnitOfWork, list_id: str) -> None:
        self.parent, self.list_id = parent, list_id

    async def run(self, work: Callable[[State], T]) -> T:
        def scoped(full: State) -> T:
            scope = self.list_id
            view = State(sequence=full.sequence, initialized_lists=full.initialized_lists & {scope})
            view.products = {k: p for k, p in full.products.items() if p.scope == scope}
            view.names = {k: n for k, n in full.names.items() if n.product_id in view.products}
            view.items = {k: i for k, i in full.items.items() if i.list_id == scope}
            view.sequence = max((i.added_order or 0 for i in view.items.values()), default=0)
            view.purchases = {k: p for k, p in full.purchases.items() if p.name_id in view.names}
            view.merges = {
                k: o for k, o in full.merges.items() if o.payload.get("list_id") == scope
            }
            view.deduplications = {
                k: o for k, o in full.deduplications.items() if o.payload.get("list_id") == scope
            }
            fields = ("products", "names", "items", "purchases", "merges", "deduplications")
            owned = {field: set(getattr(view, field)) for field in fields}
            result = work(view)
            for product in view.products.values():
                product.scope = scope
            for name in view.names.values():
                if name.product_id not in view.products:
                    raise ValueError("Cross-list product assignment is forbidden")
            for field in ("items", "purchases"):
                for record in getattr(view, field).values():
                    if record.name_id not in view.names or (
                        record.list_id != scope and record.id not in owned[field]
                    ):
                        raise ValueError("Cross-list record reference is forbidden")
            for field in ("merges", "deduplications"):
                for operation in getattr(view, field).values():
                    operation.payload["list_id"] = scope
            for field in fields:
                target = getattr(full, field)
                for key in owned[field]:
                    target.pop(key)
                target.update(getattr(view, field))
            full.initialized_lists.difference_update({scope})
            full.initialized_lists.update(view.initialized_lists & {scope})
            full.sequence = max(full.sequence, view.sequence)
            return result

        return await self.parent.run(scoped)

    async def close(self) -> None:
        """The runtime collection owns the shared database connection pool."""
