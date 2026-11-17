from alembic import context

from quiet_feed.config import Config
from quiet_feed.models import Base, SQLiteBoolean
from quiet_feed.sqlite import sqlite_engine

config = context.config
connection = config.attributes.get("connection")


def render_item(type_, item, context):
    if type_ == "type" and isinstance(item, SQLiteBoolean):
        return "sa.Integer()"
    return False


def run(connection):
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,
        render_item=render_item,
        include_object=lambda obj, name, type_, reflected, compare_to: (
            name != "__drizzle_migrations"
        ),
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Quiet Feed migrations require a database connection.")
elif connection is not None:
    run(connection)
else:
    settings = Config.from_env()
    engine = sqlite_engine(settings.database_path)
    with engine.begin() as connection:
        run(connection)
