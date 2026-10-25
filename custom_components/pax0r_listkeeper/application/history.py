"""Purchase cycles and retrospective corrections."""

from datetime import datetime

from ..domain.models import CORRECTION_WINDOW, Purchase, Snapshot, State, new_id


class RecordPurchase:
    def execute(self, state: State, item: Snapshot, at: datetime, source: str) -> None:
        key = f"{item.id}:{item.generation}:{item.cycle}"
        if any(p.idempotency_key == key for p in state.purchases.values()):
            return
        purchase = Purchase(
            new_id(),
            item.name_id,
            item.name,
            item.list_id,
            item.uid,
            at,
            "confirmed",
            source,
            key,
        )
        state.purchases[purchase.id] = purchase


class CorrectPurchase:
    def execute(self, state: State, item: Snapshot, at: datetime, trusted: bool) -> None:
        key = f"{item.id}:{item.generation}:{item.cycle}"
        for purchase in state.purchases.values():
            if (
                purchase.idempotency_key == key
                and purchase.status == "confirmed"
                and trusted
                and purchase.source == "live"
                and at >= purchase.occurred_at
                and at - purchase.occurred_at <= CORRECTION_WINDOW
            ):
                purchase.status = "cancelled"
                purchase.corrected_at = at
                purchase.correction_reason = "quick_uncheck"
        item.cycle += 1
