from datetime import datetime, timedelta

import pytest

from custom_components.pax0r_listkeeper.application.catalog import (
    MergeProductNames,
    MoveProductName,
)
from custom_components.pax0r_listkeeper.application.queries import (
    CalendarAnalytics,
    DeleteShoppingData,
    ExportShoppingData,
    GetProductCatalog,
    GetPurchaseHistory,
    GetShoppingStatistics,
)
from custom_components.pax0r_listkeeper.application.reconcile import observe_name
from custom_components.pax0r_listkeeper.domain.models import Purchase, new_id


def populate(state, names_and_dates):
    for label, dates in names_and_dates:
        name = observe_name(state, label, dates[-1])
        name.occurrences = len(dates) + 2
        for at in dates:
            identity = new_id()
            state.purchases[identity] = Purchase(
                identity, name.id, label, "list", identity, at, "confirmed", "live", identity
            )


@pytest.mark.parametrize("overlap,expected", [(False, 5), (True, 4)])
async def test_merge_retroactive_and_safe_move(memory, now, overlap, expected):
    dates = [now + timedelta(days=d) for d in (0, 1, 2)]
    other = [now + timedelta(days=d) for d in ((2, 4) if overlap else (3, 4))]
    await memory.run(lambda s: populate(s, [("Srajtaśma", dates), ("Papier toaletowy", other)]))
    original = {p.id: p.original_name for p in memory.state.purchases.values()}
    ids = list(memory.state.names)
    await MergeProductNames(memory).execute(ids, ids[1], now)
    stats = await GetShoppingStatistics(memory, CalendarAnalytics("Europe/Warsaw", now)).execute()
    assert stats["summary"]["purchases"] == expected
    assert len(stats["products"]) == 1
    assert {p.id: p.original_name for p in memory.state.purchases.values()} == original
    await MoveProductName(memory).execute(ids[0], None, now)
    stats = await GetShoppingStatistics(memory, CalendarAnalytics("Europe/Warsaw", now)).execute()
    assert len(stats["products"]) == 2
    assert stats["summary"]["purchases"] == 5
    assert len(memory.state.purchases) == 5
    assert len(memory.state.merges) == 2


async def test_catalog_counts_occurrences_separately(memory, now):
    await memory.run(lambda s: populate(s, [("A", [now]), ("B", [now, now])]))
    catalog = await GetProductCatalog(memory).execute()
    assert [(n["occurrences"], n["purchases"]) for n in catalog] == [(3, 1), (4, 2)]
    history = await GetPurchaseHistory(memory).execute(catalog[0]["id"])
    assert history["total"] == 1


async def test_frequency_filter_and_cancelled_events(memory, now):
    await memory.run(
        lambda s: populate(s, [("A", [now, now + timedelta(days=30), now + timedelta(days=60)])])
    )
    analytics = CalendarAnalytics("Europe/Warsaw", now + timedelta(days=60))
    dashboard = await GetShoppingStatistics(memory, analytics).execute(30)
    assert dashboard["products"][0]["purchases"] == 1
    assert dashboard["products"][0]["average_days"] == 30
    next(iter(memory.state.purchases.values())).status = "cancelled"
    dashboard = await GetShoppingStatistics(memory, analytics).execute()
    assert dashboard["summary"]["purchases"] == 2


@pytest.mark.parametrize(
    "times,days,average",
    [
        (
            ["2026-10-24T22:30:00+00:00", "2026-10-25T00:30:00+00:00", "2026-10-25T01:30:00+00:00"],
            1,
            None,
        ),
        (["2026-03-28T23:30:00+00:00", "2026-03-29T22:30:00+00:00"], 2, 1),
    ],
)
async def test_local_calendar_dst(memory, times, days, average):
    dates = [datetime.fromisoformat(t) for t in times]
    await memory.run(lambda s: populate(s, [("A", dates)]))
    result = await GetShoppingStatistics(
        memory, CalendarAnalytics("Europe/Warsaw", dates[-1])
    ).execute()
    assert result["products"][0]["purchases"] == days
    assert result["products"][0]["average_days"] == average


async def test_export_and_explicit_erase(memory, now):
    await memory.run(lambda s: populate(s, [("A", [now])]))
    exported = await ExportShoppingData(memory).execute()
    assert exported["format_version"] == 1
    assert next(iter(exported["data"]["purchases"].values()))["occurred_at"].endswith("+00:00")
    with pytest.raises(ValueError):
        await DeleteShoppingData(memory).execute("yes")
    assert memory.state.purchases
    await DeleteShoppingData(memory).execute("DELETE SHOPPING HISTORY")
    assert not memory.state.purchases


async def test_failed_merge_is_atomic(memory, now):
    await memory.run(lambda s: populate(s, [("A", [now]), ("B", [now])]))
    before = {n.id: n.product_id for n in memory.state.names.values()}
    with pytest.raises(KeyError):
        await MergeProductNames(memory).execute([*before, "missing"], next(iter(before)), now)
    assert {n.id: n.product_id for n in memory.state.names.values()} == before
