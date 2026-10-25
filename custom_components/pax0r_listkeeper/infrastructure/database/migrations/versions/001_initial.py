"""Initial schema, frozen independently of current ORM models."""

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None
P = "pax0r_listkeeper_"


def identity():
    return sa.Column("id", sa.String(32), primary_key=True)


def name_reference():
    return sa.Column(
        "name_id", sa.String(32), sa.ForeignKey(P + "product_names.id"), nullable=False
    )


def upgrade() -> None:
    # checkfirst permits safe retry after interrupted nontransactional MySQL DDL.
    metadata = sa.MetaData()
    sa.Table(P + "products", metadata, identity(), sa.Column("label", sa.Text, nullable=False))
    sa.Table(
        P + "product_names",
        metadata,
        identity(),
        sa.Column("product_id", sa.String(32), sa.ForeignKey(P + "products.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("normalized", sa.Text, nullable=False),
        sa.Column("normalized_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("occurrences", sa.Integer, nullable=False),
        sa.Column("last_seen", sa.String(40), nullable=False),
    )
    sa.Table(
        P + "todo_items",
        metadata,
        identity(),
        sa.Column("list_id", sa.String(100), nullable=False),
        sa.Column("uid", sa.String(100), nullable=False),
        name_reference(),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("completed", sa.Boolean, nullable=False),
        sa.Column("present", sa.Boolean, nullable=False),
        sa.Column("cycle", sa.Integer, nullable=False),
        sa.Column("generation", sa.Integer, nullable=False),
        sa.Column("first_seen", sa.String(40), nullable=False),
        sa.Column("added_order", sa.Integer, nullable=True),
        sa.UniqueConstraint("list_id", "uid"),
    )
    sa.Table(
        P + "purchase_events",
        metadata,
        identity(),
        name_reference(),
        sa.Column("original_name", sa.Text, nullable=False),
        sa.Column("list_id", sa.String(100), nullable=False),
        sa.Column("item_uid", sa.String(100), nullable=False),
        sa.Column("occurred_at", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False, unique=True),
        sa.Column("corrected_at", sa.String(40), nullable=True),
        sa.Column("correction_reason", sa.String(30), nullable=True),
    )
    for name in ("merge_operations", "deduplication_operations"):
        sa.Table(
            P + name,
            metadata,
            identity(),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("occurred_at", sa.String(40), nullable=False),
            sa.Column("payload", sa.JSON, nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
        )
    sa.Table(
        P + "control",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("initialized_lists", sa.JSON, nullable=False),
    )
    metadata.create_all(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    raise RuntimeError("Destructive migrations are disabled. Restore a backup.")
