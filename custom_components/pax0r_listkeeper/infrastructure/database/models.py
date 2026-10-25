"""SQLAlchemy 2 ORM. UTC timestamps use portable ISO-8601 strings."""

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PREFIX = "pax0r_listkeeper_"


class Base(DeclarativeBase):
    pass


class ProductRow(Base):
    __tablename__ = PREFIX + "products"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(Text)


class NameRow(Base):
    __tablename__ = PREFIX + "product_names"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey(ProductRow.id), index=True)
    name: Mapped[str] = mapped_column(Text)
    normalized: Mapped[str] = mapped_column(Text)
    # Hash avoids MySQL collation and index length altering normalization semantics.
    normalized_hash: Mapped[str] = mapped_column(String(64), unique=True)
    occurrences: Mapped[int] = mapped_column(Integer)
    last_seen: Mapped[str] = mapped_column(String(40))


class ItemRow(Base):
    __tablename__ = PREFIX + "todo_items"
    __table_args__ = (UniqueConstraint("list_id", "uid"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    list_id: Mapped[str] = mapped_column(String(100))
    uid: Mapped[str] = mapped_column(String(100))
    name_id: Mapped[str] = mapped_column(ForeignKey(NameRow.id), index=True)
    name: Mapped[str] = mapped_column(Text)
    completed: Mapped[bool] = mapped_column(Boolean)
    present: Mapped[bool] = mapped_column(Boolean)
    cycle: Mapped[int] = mapped_column(Integer)
    generation: Mapped[int] = mapped_column(Integer)
    first_seen: Mapped[str] = mapped_column(String(40))
    added_order: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PurchaseRow(Base):
    __tablename__ = PREFIX + "purchase_events"
    __table_args__ = (Index(PREFIX + "purchase_name_time", "name_id", "occurred_at"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name_id: Mapped[str] = mapped_column(ForeignKey(NameRow.id))
    original_name: Mapped[str] = mapped_column(Text)
    list_id: Mapped[str] = mapped_column(String(100))
    item_uid: Mapped[str] = mapped_column(String(100))
    occurred_at: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), index=True)
    source: Mapped[str] = mapped_column(String(20))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    corrected_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    correction_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)


class MergeRow(Base):
    __tablename__ = PREFIX + "merge_operations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    occurred_at: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20))


class DedupRow(Base):
    __tablename__ = PREFIX + "deduplication_operations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    occurred_at: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), index=True)


class ControlRow(Base):
    __tablename__ = PREFIX + "control"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer)
    initialized_lists: Mapped[list] = mapped_column(JSON)
