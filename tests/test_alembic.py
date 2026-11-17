import sqlite3

import pytest
from alembic import command
from alembic.migration import MigrationContext
from alembic.operations import Operations
from conftest import legacy_database
from sqlalchemy import Column, Text, inspect

from quiet_feed.migrate import alembic_config, migrate
from quiet_feed.sqlite import sqlite_engine


@pytest.mark.parametrize("historical", [False, True])
def test_models_and_migration_history_do_not_generate_spurious_schema_changes(config, historical):
    legacy_database(config.database_path, historical=historical)
    migrate(config.database_path)
    engine = sqlite_engine(config.database_path)
    try:
        with engine.begin() as connection:
            settings = alembic_config()
            settings.attributes["connection"] = connection
            command.check(settings)
    finally:
        engine.dispose()


def test_future_batch_migrations_preserve_legacy_foreign_key_cascades(config):
    legacy_database(config.database_path)
    migrate(config.database_path)
    engine = sqlite_engine(config.database_path)
    try:
        with engine.begin() as connection:
            operations = Operations(MigrationContext.configure(connection))
            with operations.batch_alter_table("feeds", recreate="always") as batch:
                batch.add_column(Column("example_future_column", Text, nullable=True))
            foreign_keys = inspect(connection).get_foreign_keys("feeds")
            assert foreign_keys[0]["options"]["ondelete"] == "CASCADE"
    finally:
        engine.dispose()
    with sqlite3.connect(config.database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("DELETE FROM user WHERE id='reader'")
        assert connection.execute("SELECT count(*) FROM feeds").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM articles").fetchone()[0] == 0
