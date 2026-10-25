from datetime import timedelta

import pytest

from custom_components.pax0r_listkeeper.domain.matching import (
    AliasMatcher,
    CompositeMatcher,
    DuplicateResolver,
    ExactMatcher,
    Match,
    matching_key,
    normalize,
)
from custom_components.pax0r_listkeeper.domain.models import ProductName, Snapshot


@pytest.mark.parametrize(
    "left,right",
    [
        ("  Papier   WC ", "papier wc"),
        ("MLEKO 3,2% 1L", "mleko 3,2% 1l"),
        ("Cafe\u0301", "Café"),
        ("a\t b\n", "A B"),
    ],
)
def test_normalization(left, right):
    assert normalize(left) == normalize(right)


def test_meaningful_details_preserved():
    assert normalize("mleko 2%") != normalize("mleko 3%")
    assert normalize("mleko 1l") != normalize("mleko 2l")
    assert normalize("papier") != normalize("papie")


@pytest.mark.parametrize("matcher", [ExactMatcher(), AliasMatcher(), CompositeMatcher()])
def test_approved_names_and_ambiguity(matcher, now):
    names = [ProductName("a", "p", "WC", "wc", 0, now)]
    assert matcher.match(" WC ", names).product_id == "p"
    assert matcher.match("toilet", names).product_id is None
    names.append(ProductName("b", "other", "WC", "wc", 0, now))
    assert matcher.match("wc", names).product_id is None


def test_composite_rejects_conflicting_matchers():
    class Constant:
        def __init__(self, product):
            self.product = product

        def match(self, name, names):
            return Match(self.product, "fake")

    assert CompositeMatcher(Constant("a"), Constant("b")).match("x", []).product_id is None


def test_unknown_newer_item_uses_observation_order(now):
    old = Snapshot("a", "list", "a", "name", "Milk", False, True, 0, 0, now, 1)
    offline = Snapshot(
        "b", "list", "b", "name", "Milk", False, True, 0, 0, now + timedelta(days=1), None
    )
    assert DuplicateResolver().resolve([old, offline]) == (offline, [old])


@pytest.mark.parametrize(
    "left,right", [("Mydło", "mydlo"), ("ŻÓŁĆ", "zolc"), ("ŚĆŃĄĘŹ", "scnaez"), ("Café", "cafe")]
)
def test_accent_insensitive_matching(left, right):
    assert matching_key(left) == matching_key(right)


def test_matching_keeps_quantities_and_units():
    assert matching_key("Mydło 100g") != matching_key("mydlo 200g")
    assert matching_key("Milk 2%") != matching_key("milk 3%")
