"""Add analytical and reference indexes without modifying stored events."""

from alembic import op
from sqlalchemy import inspect

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None
P = "pax0r_listkeeper_"


def upgrade() -> None:
    for table, suffix, columns in (
        ("product_names", "name_product", ["product_id"]),
        ("todo_items", "item_name", ["name_id"]),
        ("purchase_events", "purchase_name_time", ["name_id", "occurred_at"]),
        ("purchase_events", "purchase_status", ["status"]),
        ("deduplication_operations", "dedup_status", ["status"]),
    ):
        name = P + suffix
        existing = {i["name"] for i in inspect(op.get_bind()).get_indexes(P + table)}
        if name not in existing:
            op.create_index(name, P + table, columns)


def downgrade() -> None:
    raise RuntimeError("Downgrade requires restoring a backup")
