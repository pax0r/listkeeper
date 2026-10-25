"""Transactional catalog decisions preserve event/name identities."""

from datetime import datetime

from ..domain.matching import matching_key, normalize
from ..domain.models import Operation, Product, ProductName, State, new_id
from .ports import UnitOfWork


class MergeProductNames:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(
        self,
        name_ids: list[str],
        target_name_id: str,
        at: datetime,
        whole_products: bool = False,
    ) -> str:
        def merge(state: State) -> str:
            if target_name_id not in name_ids or len(set(name_ids)) < 2:
                raise ValueError("Select at least two names and a target name")
            selected = [state.names[i] for i in set(name_ids)]
            if whole_products:
                product_ids = {name.product_id for name in selected}
                selected = [n for n in state.names.values() if n.product_id in product_ids]
            target = state.names[target_name_id]
            before = {n.id: n.product_id for n in selected}
            for name in selected:
                name.product_id = target.product_id
            if not whole_products:
                state.products[target.product_id].label = target.name
            operation = Operation(
                new_id(),
                "merge_names",
                at,
                {
                    "before": before,
                    "after": target.product_id,
                    "target_name_id": target_name_id,
                    "whole_products": whole_products,
                },
                "done",
            )
            state.merges[operation.id] = operation
            return target.product_id

        return await self.uow.run(merge)


class CatalogConflict(ValueError):
    """A canonical label is already assigned to another product in this list."""


class RenameProduct:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, product_id: str, label: str, at: datetime) -> str:
        label = " ".join(label.split())
        if not label or len(label) > 500:
            raise ValueError("A product name must contain between 1 and 500 characters")

        def rename(state: State) -> str:
            product = state.products[product_id]
            key = matching_key(label)
            assigned = {name.product_id for name in state.names.values()}
            conflicts = {n.product_id for n in state.names.values() if matching_key(n.name) == key}
            conflicts.update(
                p.id
                for p in state.products.values()
                if p.id in assigned and matching_key(p.label) == key
            )
            if conflicts - {product_id}:
                raise CatalogConflict("This name belongs to another product; merge instead")
            existing = next(
                (n for n in state.names.values() if n.normalized == normalize(label)), None
            )
            if product.label == label and existing is not None:
                return product_id
            if existing is None:
                # Register approved spelling without inventing a list occurrence.
                existing = ProductName(new_id(), product_id, label, normalize(label), 0, at)
                state.names[existing.id] = existing
            before = product.label
            product.label = label
            operation = Operation(
                new_id(),
                "rename_product",
                at,
                {
                    "product_id": product_id,
                    "before": before,
                    "after": label,
                    "name_id": existing.id,
                },
                "done",
            )
            state.merges[operation.id] = operation
            return product_id

        return await self.uow.run(rename)


class MoveProductName:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, name_id: str, target_product_id: str | None, at: datetime) -> str:
        def move(state: State) -> str:
            name = state.names[name_id]
            before = name.product_id
            if target_product_id is None:
                target = Product(new_id(), name.name)
                state.products[target.id] = target
            else:
                target = state.products[target_product_id]
            name.product_id = target.id
            source = state.products[before]
            if before != target.id and normalize(source.label) == name.normalized:
                remaining = [n for n in state.names.values() if n.product_id == before]
                if remaining:
                    source.label = max(
                        remaining, key=lambda n: (n.occurrences, n.last_seen, n.id)
                    ).name
            operation = Operation(
                new_id(),
                "move_name",
                at,
                {
                    "name_id": name_id,
                    "before": before,
                    "after": target.id,
                },
                "done",
            )
            state.merges[operation.id] = operation
            return target.id

        return await self.uow.run(move)
