"""Add non-destructive catalog ownership for independently managed lists."""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None
TABLE = "pax0r_listkeeper_products"


def upgrade() -> None:
    connection = op.get_bind()
    if "scope" not in {c["name"] for c in sa.inspect(connection).get_columns(TABLE)}:
        op.add_column(TABLE, sa.Column("scope", sa.String(100), nullable=False, server_default=""))
    name = "ix_pax0r_listkeeper_products_scope"
    if name not in {i["name"] for i in sa.inspect(connection).get_indexes(TABLE)}:
        op.create_index(name, TABLE, ["scope"])


def downgrade() -> None:
    raise RuntimeError("Downgrade requires restoring a backup")
