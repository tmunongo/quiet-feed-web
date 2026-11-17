"""Standard-library helpers shared by browser and container upgrade rehearsals."""

import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRYPTO = json.loads((ROOT / "tests/fixtures/legacy-crypto.json").read_text())


def seed_legacy(path, revision=2, historical=False):
    entries = json.loads((ROOT / "drizzle/meta/_journal.json").read_text())["entries"]
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE __drizzle_migrations (id INTEGER PRIMARY KEY AUTOINCREMENT, hash TEXT NOT NULL, created_at NUMERIC)"
        )
        for entry in entries[: revision + 1]:
            source = ROOT / f"drizzle/{entry['tag']}.sql"
            if historical and entry["idx"] == 1:
                source = ROOT / "migrations/legacy/0001_gemini_2_0.sql"
            content = source.read_bytes()
            connection.executescript(content.decode())
            connection.execute(
                "INSERT INTO __drizzle_migrations(hash,created_at) VALUES (?,?)",
                (hashlib.sha256(content).hexdigest(), entry["when"]),
            )
            connection.commit()
        connection.execute(
            "INSERT INTO user(id,name,email,email_verified,created_at,updated_at) VALUES ('reader','Reader','reader@example.com',0,1700000000,1700000000)"
        )
        connection.execute(
            "INSERT INTO account(id,account_id,provider_id,user_id,password,created_at,updated_at) VALUES ('account','reader','credential','reader',?,1700000000,1700000000)",
            (CRYPTO["passwords"][0]["hash"],),
        )
        connection.execute(
            "INSERT INTO user_settings(user_id,timezone,edition_time) VALUES ('reader','UTC','23:59')"
        )
        connection.execute(
            "INSERT INTO feeds(id,user_id,url,title,category,created_at) VALUES ('feed','reader','https://example.com/rss','Original feed','Technology',1700000000)"
        )
        connection.execute(
            "INSERT INTO articles(id,feed_id,guid,title,url,content_html,fetched_at) VALUES ('article','feed','original-guid','Existing story','https://example.com/story','<p>Original content</p>',1700000000)"
        )
        connection.execute(
            "INSERT INTO editions(id,user_id,date,issue_number,created_at) VALUES ('edition','reader','2025-01-01',42,1700000000)"
        )
        connection.execute(
            "INSERT INTO edition_articles(id,edition_id,article_id,position,read,scroll_percent,scroll_offset) VALUES ('progress','edition','article',0,0,63,420)"
        )
        if revision >= 1:
            connection.execute("UPDATE user_settings SET gemini_api_key=?", (CRYPTO["ciphertext"],))
    return path
