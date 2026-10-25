"""Portable DTOs, analytics and export, independent of database dialect."""

from dataclasses import asdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..domain.models import State
from .ports import UnitOfWork


def portable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: portable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [portable(v) for v in value]
    return value


class CalendarAnalytics:
    def __init__(self, timezone: str, now: datetime) -> None:
        self.timezone, self.now = ZoneInfo(timezone), now

    def dashboard(self, state: State, days: int | None = None) -> dict:
        all_days: dict[str, set[date]] = {p: set() for p in state.products}
        for event in state.purchases.values():
            if event.status == "confirmed":
                product = state.names[event.name_id].product_id
                all_days[product].add(event.occurred_at.astimezone(self.timezone).date())
        cutoff = (
            self.now.astimezone(self.timezone).date() - timedelta(days=days - 1) if days else None
        )
        rows, visible_days = [], set()
        assigned = {n.product_id for n in state.names.values()}
        for product in state.products.values():
            if product.id not in assigned:
                continue
            full = sorted(all_days[product.id])
            filtered = [d for d in full if cutoff is None or d >= cutoff]
            visible_days.update(filtered)
            average = (full[-1] - full[0]).days / (len(full) - 1) if len(full) > 1 else None
            rows.append(
                {
                    "id": product.id,
                    "label": product.label,
                    "purchases": len(filtered),
                    "average_days": average,
                    "history_days": len(full),
                    "first_purchase": filtered[0] if filtered else None,
                    "last_purchase": filtered[-1] if filtered else None,
                }
            )
        rows.sort(key=lambda r: (-r["purchases"], r["label"].casefold()))
        return portable(
            {
                "summary": {
                    "purchases": sum(r["purchases"] for r in rows),
                    "products": len(rows),
                    "shopping_days": len(visible_days),
                    "names": len(state.names),
                },
                "products": rows,
                "frequency_scope": "all_history",
                "period_days": days,
            }
        )


class GetProductCatalog:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self) -> list[dict]:
        def catalog(state: State) -> list[dict]:
            rows = []
            for name in state.names.values():
                purchases = [
                    p
                    for p in state.purchases.values()
                    if p.name_id == name.id and p.status == "confirmed"
                ]
                rows.append(
                    {
                        **asdict(name),
                        "purchases": len(purchases),
                        "canonical_name": state.products[name.product_id].label,
                    }
                )
            rows.sort(key=lambda n: (n["occurrences"], -n["last_seen"].timestamp()))
            return portable(rows)

        return await self.uow.run(catalog)


class GetPurchaseHistory:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, name_id: str | None = None, offset: int = 0, limit: int = 100) -> dict:
        def history(state: State) -> dict:
            events = sorted(
                (p for p in state.purchases.values() if name_id is None or p.name_id == name_id),
                key=lambda p: (p.occurred_at, p.id),
                reverse=True,
            )
            return portable(
                {
                    "total": len(events),
                    "events": [
                        {
                            **asdict(p),
                            "canonical_name": state.products[
                                state.names[p.name_id].product_id
                            ].label,
                        }
                        for p in events[offset : offset + limit]
                    ],
                }
            )

        return await self.uow.run(history)


class GetShoppingStatistics:
    def __init__(self, uow: UnitOfWork, analytics: CalendarAnalytics) -> None:
        self.uow, self.analytics = uow, analytics

    async def execute(self, days: int | None = None) -> dict:
        return await self.uow.run(lambda s: self.analytics.dashboard(s, days))


class ExportShoppingData:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self) -> dict:
        return await self.uow.run(lambda s: portable({"format_version": 1, "data": asdict(s)}))


class DeleteShoppingData:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, confirmation: str) -> None:
        if confirmation != "DELETE SHOPPING HISTORY":
            raise ValueError("Invalid deletion confirmation")

        def clear(state: State) -> None:
            empty = State()
            state.__dict__.update(empty.__dict__)

        await self.uow.run(clear)
