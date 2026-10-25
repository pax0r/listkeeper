"""Transactional catalog decisions preserve event/name identities."""

from datetime import datetime

from ..domain.models import Operation, Product, State, new_id
from .ports import UnitOfWork


class MergeProductNames:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, name_ids: list[str], target_name_id: str, at: datetime) -> str:
        def merge(state: State) -> str:
            if target_name_id not in name_ids or len(set(name_ids)) < 2:
                raise ValueError("Select at least two names and a target name")
            selected = [state.names[i] for i in set(name_ids)]
            target = state.names[target_name_id]
            before = {n.id: n.product_id for n in selected}
            for name in selected:
                name.product_id = target.product_id
            state.products[target.product_id].label = target.name
            operation = Operation(
                new_id(),
                "merge_names",
                at,
                {
                    "before": before,
                    "after": target.product_id,
                    "target_name_id": target_name_id,
                },
                "done",
            )
            state.merges[operation.id] = operation
            return target.product_id

        return await self.uow.run(merge)


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
