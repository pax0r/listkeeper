"""Programmatic Alembic entry point. Never migrate Recorder tables."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, false, insert, select, update
from sqlalchemy.schema import CreateSchema

from ..models import Base, ControlRow


def upgrade(engine, revision: str = "head") -> None:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent))
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(CreateSchema("pax0r_listkeeper", if_not_exists=True))
        config.attributes["connection"] = connection
        command.upgrade(config, revision)
        # Empty statements verify DML grants without creating or changing records.
        for table in Base.metadata.sorted_tables:
            connection.execute(select(table).limit(0))
            connection.execute(
                insert(table).from_select(list(table.c), select(table).where(false()))
            )
            connection.execute(update(table).where(false()).values(id=table.c.id))
            connection.execute(delete(table).where(false()))
        if connection.scalar(select(ControlRow.id).where(ControlRow.id == 1)) is None:
            connection.execute(insert(ControlRow).values(id=1, sequence=0, initialized_lists=[]))
