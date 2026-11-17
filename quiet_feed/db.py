from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from .models import UserSettings
from .sqlite import sqlite_engine


class Database:
    def __init__(self, path):
        self.engine = sqlite_engine(path, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(self.engine, "connect")
        def configure(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=30000")

        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def transaction(self):
        with self.sessions.begin() as session:
            yield session

    def close(self):
        self.engine.dispose()


def get_settings(session, user_id):
    settings = session.get(UserSettings, user_id)
    if settings is None:
        settings = UserSettings(user_id=user_id)
        session.add(settings)
        session.flush()
    return settings
