"""Adopt a verified Drizzle database without rebuilding application tables."""

import fcntl
import hashlib
import json
import logging
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory

from .config import ROOT, Config
from .sqlite import sqlite_engine

log = logging.getLogger(__name__)


def alembic_config():
    return AlembicConfig(str(ROOT / "alembic.ini"))


def legacy_entries():
    return json.loads((ROOT / "drizzle/meta/_journal.json").read_text())["entries"]


def schema(connection):
    result = {}
    for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        if table.startswith("sqlite_") or table in {"__drizzle_migrations", "alembic_version"}:
            continue
        # Names come from SQLite, but quote them even when rejecting an unknown schema.
        quoted = '"' + table.replace('"', '""') + '"'
        columns = [tuple(row) for row in connection.execute(f"PRAGMA table_info({quoted})")]
        foreign_keys = [
            tuple(row) for row in connection.execute(f"PRAGMA foreign_key_list({quoted})")
        ]
        unique = []
        for index in connection.execute(f"PRAGMA index_list({quoted})"):
            if index[2]:
                name = '"' + index[1].replace('"', '""') + '"'
                unique.append(
                    tuple(row[2] for row in connection.execute(f"PRAGMA index_info({name})"))
                )
        result[table] = (columns, sorted(foreign_keys), sorted(unique))
    return result


def expected_schema(revision, sources=None):
    with closing(sqlite3.connect(":memory:")) as reference:
        for entry in legacy_entries():
            if entry["idx"] > int(revision):
                break
            source = sources[entry["idx"]] if sources else ROOT / f"drizzle/{entry['tag']}.sql"
            reference.executescript(source.read_text())
        return schema(reference)


def detect_revision(connection):
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if not tables:
        return None, False
    if "alembic_version" in tables:
        rows = list(connection.execute("SELECT version_num FROM alembic_version"))
        if len(rows) != 1:
            raise RuntimeError("Invalid Alembic history; refusing to alter this database.")
        revision = rows[0][0]
        if ScriptDirectory.from_config(alembic_config()).get_revision(revision) is None:
            raise RuntimeError("Unknown Alembic revision; use the matching application image.")
        return revision, False
    if "__drizzle_migrations" not in tables:
        raise RuntimeError(
            "Unrecognized database: no Drizzle or Alembic history. Database unchanged."
        )
    applied = list(
        connection.execute("SELECT hash, created_at FROM __drizzle_migrations ORDER BY created_at")
    )
    entries = legacy_entries()
    if not applied or len(applied) > len(entries):
        raise RuntimeError("Unrecognized Drizzle history. Database unchanged.")
    sources = []
    for (digest, timestamp), entry in zip(applied, entries, strict=False):
        candidates = [
            ROOT / f"drizzle/{entry['tag']}.sql",
            *sorted((ROOT / "migrations/legacy").glob(f"{entry['idx']:04d}_*.sql")),
        ]
        matching = next(
            (
                source
                for source in candidates
                if hashlib.sha256(source.read_bytes()).hexdigest() == digest
            ),
            None,
        )
        if timestamp != entry["when"] or matching is None:
            raise RuntimeError("Drizzle migration checksum mismatch. Database unchanged.")
        sources.append(matching)
    revision = f"{len(applied) - 1:04d}"
    if schema(connection) != expected_schema(revision, sources):
        raise RuntimeError(
            "Database schema does not match its Drizzle history. Database unchanged."
        )
    return revision, True


def migrate(path: Path):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Serialize startup/CLI migrations, including the backup and history adoption.
    with path.with_suffix(path.suffix + ".migration.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with closing(sqlite3.connect(path)) as connection:
            revision, adopting = detect_revision(connection)
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("SQLite integrity check failed; refusing to migrate.")
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise RuntimeError("SQLite foreign key check failed; refusing to migrate.")
            head = ScriptDirectory.from_config(alembic_config()).get_current_head()
            backup = None
            if revision is not None and (adopting or revision != head):
                directory = path.parent / "backups"
                directory.mkdir(exist_ok=True, mode=0o700)
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                backup = directory / f"{path.stem}-pre-python-{stamp}-{uuid4().hex[:8]}.db"
                with closing(sqlite3.connect(backup)) as destination:
                    connection.backup(destination)
                backup.chmod(0o600)
                log.info("Pre-migration SQLite backup: %s", backup)
        engine = sqlite_engine(path)
        try:
            with engine.begin() as connection:
                # Ensure SQLite DDL participates in the same transaction as history changes.
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                cfg = alembic_config()
                cfg.attributes["connection"] = connection
                if adopting:
                    command.stamp(cfg, revision)
                command.upgrade(cfg, "head")
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            with engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        finally:
            engine.dispose()
        return backup


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    settings = Config.from_env()
    settings.validate()
    migrate(settings.database_path)
