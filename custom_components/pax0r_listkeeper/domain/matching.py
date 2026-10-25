"""Deterministic identity matching and conservative duplicate resolution."""

import unicodedata
from dataclasses import dataclass
from typing import Protocol

from .models import ProductName, Snapshot


def normalize(name: str) -> str:
    return " ".join(unicodedata.normalize("NFC", name).casefold().split())


@dataclass(frozen=True)
class Match:
    product_id: str | None
    basis: str


class ProductMatcher(Protocol):
    def match(self, name: str, names: list[ProductName]) -> Match: ...


class ExactMatcher:
    def match(self, name: str, names: list[ProductName]) -> Match:
        matches = {n.product_id for n in names if n.normalized == normalize(name)}
        return (
            Match(next(iter(matches)), "normalized_exact")
            if len(matches) == 1
            else Match(None, "unknown_or_ambiguous")
        )


class AliasMatcher(ExactMatcher):
    def match(self, name: str, names: list[ProductName]) -> Match:
        result = super().match(name, names)
        return Match(result.product_id, "approved_alias" if result.product_id else result.basis)


class CompositeMatcher:
    def __init__(self, *matchers: ProductMatcher) -> None:
        self.matchers = matchers or (ExactMatcher(), AliasMatcher())

    def match(self, name: str, names: list[ProductName]) -> Match:
        results = [m.match(name, names) for m in self.matchers]
        ids = {r.product_id for r in results if r.product_id}
        if len(ids) != 1:
            return Match(None, "unknown_or_ambiguous")
        return next(r for r in results if r.product_id)


class DuplicateResolver:
    """Only delete when observation order identifies an unambiguous new item."""

    def resolve(self, items: list[Snapshot]) -> tuple[Snapshot, list[Snapshot]] | None:
        ordered = [i for i in items if i.added_order is not None]
        if len(items) < 2 or not ordered:
            return None
        newest = max(ordered, key=lambda i: i.added_order)
        if newest.completed or any(
            i.added_order is None and i.first_seen > newest.first_seen for i in items
        ):
            return None
        return newest, [i for i in items if i.id != newest.id]
