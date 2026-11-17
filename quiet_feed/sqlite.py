"""SQLite reflection that preserves Drizzle's backtick-quoted foreign keys."""

from sqlalchemy import create_engine
from sqlalchemy.dialects import registry
from sqlalchemy.dialects.sqlite.pysqlite import SQLiteDialect_pysqlite


class QuietFeedSQLiteDialect(SQLiteDialect_pysqlite):
    supports_statement_cache = True

    def get_foreign_keys(self, connection, table_name, schema=None, **kwargs):
        reflected = super().get_foreign_keys(connection, table_name, schema=schema, **kwargs)
        # SQLAlchemy's DDL regex misses REFERENCES `table` (`column`). Read the
        # authoritative actions from SQLite so Alembic never silently loses a
        # cascade during a future batch migration or proposes spurious FK edits.
        quote = self.identifier_preparer.quote_identifier
        namespace = f"{quote(schema)}." if schema else ""
        rows = connection.exec_driver_sql(
            f"PRAGMA {namespace}foreign_key_list({quote(table_name)})"
        ).all()
        groups = {}
        for row in rows:
            groups.setdefault(row[0], []).append(row)
        for foreign_key in reflected:
            for group in groups.values():
                if (
                    foreign_key["constrained_columns"] == [row[3] for row in group]
                    and foreign_key["referred_table"] == group[0][2]
                ):
                    for key, index in [("onupdate", 5), ("ondelete", 6)]:
                        action = group[0][index]
                        if action != "NO ACTION":
                            foreign_key["options"][key] = action
        return reflected


registry.register("sqlite.quiet_feed", "quiet_feed.sqlite", "QuietFeedSQLiteDialect")


def sqlite_engine(path, **kwargs):
    return create_engine(f"sqlite+quiet_feed:///{path}", **kwargs)
