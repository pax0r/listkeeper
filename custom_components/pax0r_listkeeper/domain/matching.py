"""Deterministic identity matching and conservative duplicate resolution."""

import unicodedata
from dataclasses import dataclass
from typing import Protocol

from .models import ProductName, Snapshot


def normalize(name: str) -> str:
    return " ".join(unicodedata.normalize("NFC", name).casefold().split())


def matching_key(name: str) -> str:
    """Fold accents for matching while retaining original catalog identities."""
    decomposed = unicodedata.normalize("NFD", normalize(name).replace("ł", "l"))
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class Match:
    product_id: str | None
    basis: str


class ProductMatcher(Protocol):
    def match(self, name: str, names: list[ProductName]) -> Match: ...


class ExactMatcher:
    def match(self, name: str, names: list[ProductName]) -> Match:
        matches = {n.product_id for n in names if matching_key(n.name) == matching_key(name)}
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
    """Keep one item per identity, preferring an outstanding shopping task."""

    def resolve(self, items: list[Snapshot]) -> tuple[Snapshot, list[Snapshot]] | None:
        if len(items) < 2:
            return None
        candidates = [i for i in items if not i.completed] or items
        # Observation time is not a claim about an offline item's creation time.
        # UID provides a repeatable tie-break for pre-existing baseline items.
        newest = max(candidates, key=lambda i: (i.first_seen, i.added_order or -1, i.uid))
        return newest, [i for i in items if i.id != newest.id]
