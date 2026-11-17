from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import delete, func, select

from quiet_feed import editions, feeds
from quiet_feed.models import Article, Edition, EditionArticle, Feed, UserSettings


@pytest.fixture(autouse=True)
def stub_feeds(monkeypatch):
    monkeypatch.setattr(feeds, "fetch_all", lambda *_: [])


def selection(database):
    edition_id, _ = editions.compile_edition(database, "reader")
    view = editions.edition_view(database, edition_id, "reader")
    stories = [story for rows in view["categories"].values() for story in rows]
    return view, stories


def test_default_budget_source_sharing_and_newest_first(database):
    view, stories = selection(database)
    assert view["total"] == 20
    assert [sum(story["feed"].id == feed for story in stories) for feed in "abc"] == [7, 7, 6]
    assert [story["article"].title for story in stories if story["feed"].id == "a"] == [
        f"a-{i}" for i in range(7)
    ]


def test_per_feed_caps_and_spare_slots(database):
    with database.transaction() as session:
        session.get(Feed, "a").article_cap = 5
        session.get(UserSettings, "reader").edition_article_cap = 100
    view, stories = selection(database)
    assert view["total"] == 35
    assert sum(story["feed"].id == "a" for story in stories) == 5


def test_rotating_sources_and_no_repeated_articles(database):
    with database.transaction() as session:
        session.get(UserSettings, "reader").edition_article_cap = 2
    first, stories = selection(database)
    assert [story["feed"].id for story in stories] == ["a", "b"]
    with database.transaction() as session:
        session.get(Edition, first["edition"].id).date = "2000-01-01"
    second, next_stories = selection(database)
    assert [story["feed"].id for story in next_stories] == ["b", "c"]
    assert not {s["article"].id for s in stories} & {s["article"].id for s in next_stories}


def test_changing_budget_does_not_change_frozen_issue(database):
    first, stories = selection(database)
    with database.transaction() as session:
        session.get(UserSettings, "reader").edition_article_cap = 1
    second, next_stories = selection(database)
    assert first["edition"].id == second["edition"].id
    assert [s["article"].id for s in stories] == [s["article"].id for s in next_stories]


def test_simultaneous_compilation_publishes_one_complete_issue(database):
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(lambda _: editions.compile_edition(database, "reader"), range(4))
        )
    assert len({result[0] for result in results}) == 1
    with database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(Edition)) == 1
        assert session.scalar(select(func.count()).select_from(EditionArticle)) == 20


def test_empty_backlog_is_a_quiet_day(database):
    with database.transaction() as session:
        session.execute(delete(Article))
    view, _ = selection(database)
    assert view["total"] == 0
    assert view["edition"].closed_at is None


def test_due_time_uses_user_timezone_and_existing_edition(database, monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    monkeypatch.setattr(
        editions,
        "local_now",
        lambda settings: datetime(2026, 3, 10, 6, 59, tzinfo=ZoneInfo(settings.timezone)),
    )
    assert not editions.is_due(database, "reader")
    monkeypatch.setattr(
        editions,
        "local_now",
        lambda settings: datetime(2026, 3, 10, 7, 0, tzinfo=ZoneInfo(settings.timezone)),
    )
    assert editions.is_due(database, "reader")
    editions.get_or_compile(database, "reader")
    assert not editions.is_due(database, "reader")
