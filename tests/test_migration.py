import sqlite3

import pytest
from conftest import CRYPTO, csrf, legacy_database
from fastapi.testclient import TestClient

from quiet_feed.app import create_app
from quiet_feed.migrate import expected_schema, migrate, schema
from quiet_feed.security import decrypt_secret


def records(connection):
    connection.row_factory = sqlite3.Row
    return {
        table: [
            dict(row)
            for row in connection.execute(
                f'SELECT * FROM "{table}" ORDER BY id'
                if table != "user_settings"
                else "SELECT * FROM user_settings ORDER BY user_id"
            )
        ]
        for table in schema(connection)
    }


@pytest.mark.parametrize("revision", [0, 1, 2])
def test_upgrade_preserves_every_legacy_value_and_backs_up_wal(config, revision):
    path = legacy_database(config.database_path, revision)
    with sqlite3.connect(path) as live:
        live.execute("PRAGMA journal_mode=WAL")
        live.execute("UPDATE user SET name='Latest WAL write'")
        live.commit()
        before = records(live)
        backup = migrate(path)
        assert backup and backup.is_file()
        with sqlite3.connect(backup) as saved:
            assert records(saved) == before
        with sqlite3.connect(path) as upgraded:
            assert schema(upgraded) == expected_schema("0002")
            after = records(upgraded)
            for table, rows in before.items():
                assert len(rows) == len(after[table])
                for old, new in zip(rows, after[table], strict=True):
                    assert all(new[column] == value for column, value in old.items())
            assert upgraded.execute("PRAGMA foreign_key_check").fetchall() == []
        assert migrate(path) is None
        assert len(list((path.parent / "backups").glob("*.db"))) == 1


@pytest.mark.parametrize("kind", ["unknown", "checksum", "schema", "foreign-key"])
def test_unrecognized_database_is_left_unchanged(tmp_path, kind):
    path = tmp_path / "invalid.db"
    if kind == "unknown":
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE unrelated(value TEXT)")
    else:
        legacy_database(path)
        with sqlite3.connect(path) as connection:
            if kind == "checksum":
                connection.execute("UPDATE __drizzle_migrations SET hash='unknown'")
            elif kind == "schema":
                connection.execute("ALTER TABLE feeds ADD COLUMN unexpected TEXT")
            else:
                connection.execute("UPDATE feeds SET user_id='missing-user'")
    before = path.read_bytes()
    with pytest.raises(RuntimeError):
        migrate(path)
    assert path.read_bytes() == before
    assert not (path.parent / "backups").exists()


def test_failed_upgrade_rolls_back_schema_and_history(tmp_path, monkeypatch):
    path = legacy_database(tmp_path / "old.db", 0)
    from quiet_feed import migrate as module

    def fail(config, target):
        config.attributes["connection"].exec_driver_sql("CREATE TABLE partial_change(value TEXT)")
        raise RuntimeError("Synthetic migration failure")

    monkeypatch.setattr(module.command, "upgrade", fail)
    with pytest.raises(RuntimeError, match="Synthetic"):
        migrate(path)
    with sqlite3.connect(path) as connection:
        assert "partial_change" not in schema(connection)
        assert not connection.execute(
            "SELECT name FROM sqlite_master WHERE name='alembic_version'"
        ).fetchall()
        assert schema(connection) == expected_schema("0000")
    assert len(list((path.parent / "backups").glob("*.db"))) == 1


def test_upgrade_login_and_existing_links(config):
    legacy_database(config.database_path)
    with TestClient(create_app(config)) as client:
        client.get("/login")
        response = client.post(
            "/login",
            data={"email": "reader@example.com", "password": CRYPTO["passwords"][0]["password"]},
            headers=csrf(client),
        )
        assert response.status_code == 200
        assert "Issue №42" in client.get("/archive").text
        article = client.get("/article/progress")
        assert "Existing story" in article.text
        assert 'data-scroll-offset="420"' in article.text
        assert "/archive/2025-01-01" in article.text
        assert "Original content" in article.text
        assert "Existing story" in client.get("/dispatch?date=2025-01-01").text
        settings = client.get("/settings")
        assert 'data-theme="dark"' in settings.text
        assert "synthe••••••••7890" in settings.text
        assert CRYPTO["api_key"] not in settings.text
        assert CRYPTO["ciphertext"] not in settings.text
        assert decrypt_secret(CRYPTO["ciphertext"], config) == CRYPTO["api_key"]


def test_original_schema_remains_compatible_after_python_writes(config):
    legacy_database(config.database_path)
    with TestClient(create_app(config)) as client:
        client.get("/login")
        client.post(
            "/login",
            data={"email": "reader@example.com", "password": CRYPTO["passwords"][0]["password"]},
            headers=csrf(client),
        )
        assert (
            client.post(
                "/article/progress/progress",
                json={"read": True, "scrollOffset": 900},
                headers=csrf(client),
            ).status_code
            == 200
        )

    with sqlite3.connect(config.database_path) as connection:
        assert schema(connection) == expected_schema("0002")
        assert connection.execute(
            "SELECT read,scroll_offset FROM edition_articles WHERE id='progress'"
        ).fetchone() == (1, 900)
        assert (
            connection.execute("SELECT password FROM account WHERE id='account'").fetchone()[0]
            == CRYPTO["passwords"][0]["hash"]
        )


@pytest.mark.parametrize("revision", [1, 2])
def test_historical_deployed_gemini_default_is_adopted_without_rewriting_it(config, revision):
    legacy_database(config.database_path, revision, historical=True)
    with sqlite3.connect(config.database_path) as connection:
        before = records(connection)
    backup = migrate(config.database_path)
    assert backup.is_file()
    with sqlite3.connect(config.database_path) as connection:
        assert (
            connection.execute("PRAGMA table_info(user_settings)").fetchall()[9][4]
            == "'gemini-2.0-flash'"
        )
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002"
        after = records(connection)
        for table, rows in before.items():
            for old, new in zip(rows, after[table], strict=True):
                assert all(new[column] == value for column, value in old.items())
    assert migrate(config.database_path) is None
