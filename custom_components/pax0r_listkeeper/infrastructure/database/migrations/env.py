"""Use the integration's independent engine and prefixed version table."""

from alembic import context

connection = context.config.attributes["connection"]
context.configure(
    connection=connection,
    version_table="pax0r_listkeeper_alembic_version",
    transactional_ddl=connection.dialect.name != "mysql",
)
with context.begin_transaction():
    context.run_migrations()
