import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from quiet_feed.app import CSRF_COOKIE, create_app
from quiet_feed.config import ROOT, Config
from quiet_feed.db import Database
from quiet_feed.migrate import migrate
from quiet_feed.models import Article, Feed, User, UserSettings

CRYPTO = json.loads((Path(__file__).parent / "fixtures/legacy-crypto.json").read_text())


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    import httpx

    from quiet_feed import feeds

    monkeypatch.setattr(feeds, "download_feed", lambda *_args, **_kwargs: (304, {}, b""))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Tests must stub external HTTP requests.")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)


def legacy_database(path, revision=2, seed=True, historical=False):
    journal = json.loads((ROOT / "drizzle/meta/_journal.json").read_text())["entries"]
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE __drizzle_migrations (id INTEGER PRIMARY KEY AUTOINCREMENT, hash TEXT NOT NULL, created_at NUMERIC)"
        )
        for entry in journal[: revision + 1]:
            source = ROOT / f"drizzle/{entry['tag']}.sql"
            if historical and entry["idx"] == 1:
                source = ROOT / "migrations/legacy/0001_gemini_2_0.sql"
            sql = source.read_text()
            connection.executescript(sql)
            connection.execute(
                "INSERT INTO __drizzle_migrations(hash,created_at) VALUES (?,?)",
                (hashlib.sha256(sql.encode()).hexdigest(), entry["when"]),
            )
            connection.commit()
        if seed:
            connection.execute(
                "INSERT INTO user(id,name,email,email_verified,created_at,updated_at) VALUES ('reader','Reader','reader@example.com',0,1700000000,1700000000)"
            )
            connection.execute(
                "INSERT INTO account(id,account_id,provider_id,user_id,password,created_at,updated_at) VALUES ('account','reader','credential','reader',?,1700000000,1700000000)",
                (CRYPTO["passwords"][0]["hash"],),
            )
            connection.execute(
                "INSERT INTO user_settings(user_id,timezone,theme,collapsed_categories) VALUES ('reader','Africa/Harare','dark','[\"Technology\"]')"
            )
            connection.execute(
                "INSERT INTO feeds(id,user_id,url,title,category,etag,last_modified,created_at) VALUES ('feed','reader','https://example.com/rss','Original feed','Technology','etag-original','yesterday',1700000000)"
            )
            connection.execute(
                "INSERT INTO articles(id,feed_id,guid,title,url,content_html,fetched_at) VALUES ('article','feed','original-guid','Existing story','https://example.com/story','<p>Original content</p>',1700000000)"
            )
            connection.execute(
                "INSERT INTO editions(id,user_id,date,issue_number,created_at) VALUES ('edition','reader','2025-01-01',42,1700000000)"
            )
            connection.execute(
                "INSERT INTO edition_articles(id,edition_id,article_id,position,read,scroll_percent,scroll_offset,updated_at) VALUES ('progress','edition','article',0,0,63,420,1700000000)"
            )
            if revision >= 1:
                connection.execute(
                    "UPDATE user_settings SET gemini_api_key=?,ai_digest_enabled=1",
                    (CRYPTO["ciphertext"],),
                )
                connection.execute(
                    "INSERT INTO edition_summaries(id,edition_id,content_markdown,model,status,created_at) VALUES ('summary','edition','### The Lead\n\n[Existing story](/article/progress)','original-model','completed',1700000000)"
                )
            if revision >= 2:
                connection.execute("UPDATE editions SET closed_at=1700000001")
                connection.execute("UPDATE user_settings SET edition_article_cap=8")
    return path


@pytest.fixture
def config(tmp_path):
    return Config(
        database_path=tmp_path / "quiet-feed.db",
        secret=CRYPTO["secret"],
        cron_secret="test-cron-secret",
    )


@pytest.fixture
def database(config):
    migrate(config.database_path)
    database = Database(config.database_path)
    with database.transaction() as session:
        session.add(User(id="reader", name="Reader", email="reader@example.com"))
        session.flush()
        session.add(UserSettings(user_id="reader", timezone="UTC"))
        for feed_id in ["a", "b", "c"]:
            session.add(
                Feed(
                    id=feed_id,
                    user_id="reader",
                    url=f"https://example.com/{feed_id}",
                    title=feed_id,
                )
            )
        session.flush()
        for feed_id in ["a", "b", "c"]:
            for index in range(25):
                session.add(
                    Article(
                        id=f"{feed_id}-{index}",
                        feed_id=feed_id,
                        guid=str(index),
                        title=f"{feed_id}-{index}",
                        url="https://example.com/story",
                        published_at=1700000000 - index,
                        fetched_at=1700000000,
                    )
                )
    yield database
    database.close()


@pytest.fixture
def client(config):
    with TestClient(create_app(config)) as client:
        client.get("/register")
        yield client


def csrf(client):
    return {"X-CSRF-Token": client.cookies[CSRF_COOKIE]}


def register(client, email="test@example.com"):
    response = client.post(
        "/register",
        data={"name": "Reader", "email": email, "password": "test-password"},
        headers=csrf(client),
    )
    assert response.status_code == 200
    return response
