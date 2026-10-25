"""Stable identities and portable domain records."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import uuid4

CORRECTION_WINDOW = timedelta(hours=1)


def new_id() -> str:
    return uuid4().hex


@dataclass(frozen=True)
class ListItem:
    uid: str
    name: str
    completed: bool


@dataclass
class Product:
    id: str
    label: str


@dataclass
class ProductName:
    id: str
    product_id: str
    name: str
    normalized: str
    occurrences: int
    last_seen: datetime


@dataclass
class Snapshot:
    id: str
    list_id: str
    uid: str
    name_id: str
    name: str
    completed: bool
    present: bool
    cycle: int
    generation: int
    first_seen: datetime
    # None means order cannot be established (baseline/offline batch).
    added_order: int | None = None


@dataclass
class Purchase:
    id: str
    name_id: str
    original_name: str
    list_id: str
    item_uid: str
    occurred_at: datetime
    status: str
    source: str
    idempotency_key: str
    corrected_at: datetime | None = None
    correction_reason: str | None = None


@dataclass
class Operation:
    id: str
    kind: str
    occurred_at: datetime
    payload: dict
    status: str = "pending"


@dataclass
class State:
    products: dict[str, Product] = field(default_factory=dict)
    names: dict[str, ProductName] = field(default_factory=dict)
    items: dict[str, Snapshot] = field(default_factory=dict)
    purchases: dict[str, Purchase] = field(default_factory=dict)
    merges: dict[str, Operation] = field(default_factory=dict)
    deduplications: dict[str, Operation] = field(default_factory=dict)
    initialized_lists: set[str] = field(default_factory=set)
    sequence: int = 0
