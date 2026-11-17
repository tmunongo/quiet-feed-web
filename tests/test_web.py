import json

import pytest
from conftest import CRYPTO, csrf, legacy_database, register
from fastapi.testclient import TestClient
from sqlalchemy import select

from quiet_feed.app import create_app
from quiet_feed.models import EditionArticle, Feed, UserSettings


def login(client):
    client.get("/login")
    response = client.post(
        "/login",
        data={"email": "reader@example.com", "password": CRYPTO["passwords"][0]["password"]},
        headers=csrf(client),
    )
    assert response.status_code == 200


def settings_form(**changes):
    return {
        "editionTime": "07:00",
        "timezone": "Africa/Harare",
        "theme": "dark",
        "defaultArticleCap": "15",
        "editionArticleCap": "20",
        **changes,
    }


def test_pages_htmx_and_static_assets(client):
    register(client)
    for path in ["/", "/feeds", "/settings", "/archive"]:
        response = client.get(path)
        assert response.status_code == 200
        assert '<main id="main">' in response.text
        assert "<!doctype html>" in response.text
    partial = client.get("/feeds", headers={"HX-Request": "true"})
    assert '<main id="main">' in partial.text
    assert "<!doctype html>" not in partial.text
    assert "HX-Request" in partial.headers["vary"]
    restored = client.get(
        "/feeds", headers={"HX-Request": "true", "HX-History-Restore-Request": "true"}
    )
    assert "<!doctype html>" in restored.text
    for path in [
        "/static/app.css",
        "/static/app.js",
        "/static/vendor/htmx.min.js",
        "/static/vendor/alpine.min.js",
        "/static/fonts/fraunces-latin-wght-normal.woff2",
        "/icons/icon-source.svg",
    ]:
        assert client.get(path).status_code == 200


def test_close_preserves_progress_and_other_user_cannot_mutate(config):
    legacy_database(config.database_path)
    with TestClient(create_app(config)) as client:
        login(client)
        db = client.app.state.database
        with db.transaction() as session:
            before = session.get(EditionArticle, "progress")
            values = (before.read, before.scroll_percent, before.scroll_offset)
        assert client.post("/edition/edition/close", headers=csrf(client)).status_code == 200
        with db.transaction() as session:
            progress = session.get(EditionArticle, "progress")
            assert (progress.read, progress.scroll_percent, progress.scroll_offset) == values
        client.post("/logout", headers=csrf(client))
        register(client, "someone-else@example.com")
        for path in [
            "/article/progress",
            "/archive/2025-01-01",
            "/dispatch?date=2025-01-01",
            "/edition/edition/summary",
        ]:
            assert client.get(path).status_code == 404
        for path, data in [
            ("/edition/edition/close", {}),
            ("/edition/edition/summary", {}),
            ("/feeds/delete", {"id": "feed"}),
        ]:
            assert client.post(path, data=data, headers=csrf(client)).status_code == 404
        assert (
            client.post(
                "/article/progress/progress", json={"read": True}, headers=csrf(client)
            ).status_code
            == 404
        )


def test_progress_validation_clamping_and_persistence(config):
    legacy_database(config.database_path)
    with TestClient(create_app(config)) as client:
        login(client)
        response = client.post(
            "/article/progress/progress",
            json={"scrollPercent": 200, "scrollOffset": -1, "read": True},
            headers=csrf(client),
        )
        assert response.json() == {"ok": True}
        with client.app.state.database.transaction() as session:
            row = session.get(EditionArticle, "progress")
            assert (row.scroll_percent, row.scroll_offset, row.read) == (100, 0, True)
        assert (
            client.post(
                "/article/progress/progress",
                json={"scrollPercent": "invalid"},
                headers=csrf(client),
            ).status_code
            == 422
        )


@pytest.mark.parametrize("value", ["", "0", "-1", "101", "1.5", "NaN", "Infinity"])
def test_settings_reject_invalid_edition_budgets(client, value):
    register(client)
    response = client.post(
        "/settings", data=settings_form(editionArticleCap=value), headers=csrf(client)
    )
    assert "error-message" in response.text
    with client.app.state.database.transaction() as session:
        assert session.scalar(select(UserSettings)).edition_article_cap == 20


@pytest.mark.parametrize(
    "changes",
    [
        {"editionTime": "25:99"},
        {"timezone": "Mars/Olympus"},
        {"theme": "invalid"},
        {"defaultArticleCap": "1"},
    ],
)
def test_settings_validate_time_timezone_theme_and_caps(client, changes):
    register(client)
    response = client.post("/settings", data=settings_form(**changes), headers=csrf(client))
    assert "error-message" in response.text


def test_settings_update_preserves_key_and_collapsed_preferences(config):
    legacy_database(config.database_path)
    with TestClient(create_app(config)) as client:
        login(client)
        response = client.post(
            "/settings",
            data=settings_form(editionArticleCap="12", aiDigestEnabled="on"),
            headers=csrf(client),
        )
        assert response.status_code == 200
        assert "Settings saved." in response.text
        with client.app.state.database.transaction() as session:
            settings = session.get(UserSettings, "reader")
            assert settings.edition_article_cap == 12
            assert settings.gemini_api_key == CRYPTO["ciphertext"]
        response = client.post(
            "/api/settings/collapsed-categories",
            json={"collapsed": ["Technology", "News"]},
            headers=csrf(client),
        )
        assert response.json() == {"ok": True}
        with client.app.state.database.transaction() as session:
            assert json.loads(session.get(UserSettings, "reader").collapsed_categories) == [
                "Technology",
                "News",
            ]


def test_feed_forms_opml_roundtrip_and_invalid_import_rollback(client, monkeypatch):
    from quiet_feed import feeds

    register(client)
    monkeypatch.setattr(feeds, "discover_title", lambda url: "Test source")
    monkeypatch.setattr(feeds, "fetch_feed", lambda *_: {})
    headers = {**csrf(client), "HX-Request": "true"}
    assert (
        "Test source"
        in client.post(
            "/feeds/add",
            data={"url": "https://example.com/rss", "category": "Science"},
            headers=headers,
        ).text
    )
    with client.app.state.database.transaction() as session:
        feed = session.scalar(select(Feed))
    response = client.post(
        "/feeds/update",
        data={
            "id": feed.id,
            "url": feed.url,
            "title": "Renamed source",
            "category": "News",
            "articleCap": "3",
        },
        headers=headers,
    )
    assert "Renamed source" in response.text
    exported = client.get("/feeds/export")
    assert exported.headers["content-disposition"].endswith('"quiet-feed.opml"')
    assert b"Renamed source" in exported.content
    imported = client.post(
        "/feeds/import",
        files={"opml": ("feeds.opml", exported.content, "application/xml")},
        headers=headers,
    )
    assert "Imported 0 of 1 feeds" in imported.text
    broken = b'<opml><body><outline xmlUrl="https://other.example/rss"/><outline xmlUrl="file:///etc/passwd"/></body></opml>'
    client.post(
        "/feeds/import", files={"opml": ("feeds.opml", broken, "application/xml")}, headers=headers
    )
    with client.app.state.database.transaction() as session:
        assert len(list(session.scalars(select(Feed)))) == 1
    assert (
        "Feed removed" in client.post("/feeds/delete", data={"id": feed.id}, headers=headers).text
    )


def test_cron_requires_bearer_secret_but_no_csrf(client):
    assert client.post("/api/cron/compile").status_code == 401
    assert (
        client.post("/api/cron/compile", headers={"Authorization": "Bearer wrong"}).status_code
        == 401
    )
    response = client.post(
        "/api/cron/compile", headers={"Authorization": "Bearer test-cron-secret"}
    )
    assert response.json() == {"checked": 0, "compiled": 0, "failed": []}


def test_service_worker_retirement_is_served_at_original_url(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["service-worker-allowed"] == "/"
    assert "self.registration.unregister()" in response.text


def test_htmx_settings_redirect_reloads_document_and_theme(client):
    register(client)
    response = client.post(
        "/settings",
        data=settings_form(theme="light"),
        headers={**csrf(client), "HX-Request": "true"},
    )
    assert response.status_code == 200
    assert response.headers["HX-Redirect"] == "/settings?saved=1"
    assert 'data-theme="light"' in client.get(response.headers["HX-Redirect"]).text


def test_ordinary_feed_forms_redirect_to_canonical_page(client, monkeypatch):
    from quiet_feed import feeds

    register(client)
    monkeypatch.setattr(feeds, "discover_title", lambda _: "New source")
    response = client.post(
        "/feeds/add",
        data={"url": "https://example.com/feed"},
        headers=csrf(client),
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/feeds?")
    assert "New source" in client.get(response.headers["location"]).text
