from collections import defaultdict
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from . import feeds as feed_service
from .db import get_settings
from .models import Article, Edition, EditionArticle, EditionSummary, Feed, UserSettings, identifier


def local_now(settings):
    return datetime.now(UTC).astimezone(ZoneInfo(settings.timezone))


def todays_edition(database, user_id):
    with database.transaction() as session:
        settings = get_settings(session, user_id)
        today = local_now(settings).date().isoformat()
        return session.scalar(
            select(Edition).where(Edition.user_id == user_id, Edition.date == today)
        )


def is_due(database, user_id):
    with database.transaction() as session:
        settings = get_settings(session, user_id)
        current = local_now(settings)
        if (
            current.strftime("%H:%M") < settings.edition_time
            or settings.last_edition_date == current.date().isoformat()
        ):
            return False
    return todays_edition(database, user_id) is None


def compile_edition(database, user_id):
    existing = todays_edition(database, user_id)
    if existing:
        return existing.id, False
    feed_service.fetch_all(database, user_id)
    with database.transaction() as session:
        settings = get_settings(session, user_id)
        today = local_now(settings).date().isoformat()
    try:
        with database.transaction() as session:
            # Serialize selection/publication, including concurrent scheduler and HTTP requests.
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            existing = session.scalar(
                select(Edition).where(Edition.user_id == user_id, Edition.date == today)
            )
            if existing:
                return existing.id, False
            settings = get_settings(session, user_id)
            sources = session.scalars(select(Feed).where(Feed.user_id == user_id).order_by(Feed.id))
            prior = session.scalar(
                select(func.count()).select_from(Edition).where(Edition.user_id == user_id)
            )
            candidates = []
            shown = select(EditionArticle.article_id)
            for feed in sources:
                rows = list(
                    session.scalars(
                        select(Article.id)
                        .where(Article.feed_id == feed.id, Article.id.not_in(shown))
                        .order_by(
                            Article.published_at.desc(), Article.fetched_at.desc(), Article.id
                        )
                        .limit(
                            min(
                                feed.article_cap
                                if feed.article_cap is not None
                                else settings.default_article_cap,
                                settings.edition_article_cap,
                            )
                        )
                    )
                )
                if rows:
                    candidates.append(rows)
            selected = []
            if candidates:
                start = prior % len(candidates)
                ordered = candidates[start:] + candidates[:start]
                for index in range(max(map(len, ordered))):
                    for source in ordered:
                        if index < len(source) and len(selected) < settings.edition_article_cap:
                            selected.append(source[index])
                    if len(selected) >= settings.edition_article_cap:
                        break
            edition = Edition(id=identifier(), user_id=user_id, date=today, issue_number=prior + 1)
            session.add(edition)
            session.flush()
            session.add_all(
                EditionArticle(edition_id=edition.id, article_id=article_id, position=position)
                for position, article_id in enumerate(selected)
            )
            settings.last_edition_date = today
            return edition.id, True
    except IntegrityError:
        existing = todays_edition(database, user_id)
        if existing:
            return existing.id, False
        raise


def get_or_compile(database, user_id):
    if is_due(database, user_id):
        compile_edition(database, user_id)
    return todays_edition(database, user_id)


def edition_view(database, edition_id, user_id):
    with database.transaction() as session:
        edition = session.scalar(
            select(Edition).where(Edition.id == edition_id, Edition.user_id == user_id)
        )
        if not edition:
            return None
        rows = session.execute(
            select(EditionArticle, Article, Feed)
            .join(Article, EditionArticle.article_id == Article.id)
            .join(Feed, Article.feed_id == Feed.id)
            .where(EditionArticle.edition_id == edition_id)
            .order_by(EditionArticle.position)
        ).all()
        groups = defaultdict(list)
        for progress, article, feed in rows:
            groups[feed.category].append({"progress": progress, "article": article, "feed": feed})
        summary = session.scalar(
            select(EditionSummary).where(EditionSummary.edition_id == edition_id)
        )
        return {
            "edition": edition,
            "categories": dict(sorted(groups.items())),
            "summary": summary,
            "total": len(rows),
            "read_count": sum(row[0].read for row in rows),
        }


def compile_due(database):
    with database.transaction() as session:
        ids = list(session.scalars(select(UserSettings.user_id)))
    compiled, failed = [], []
    for user_id in ids:
        try:
            if is_due(database, user_id):
                compile_edition(database, user_id)
                compiled.append(user_id)
        except Exception:
            failed.append(
                {"userId": user_id, "message": "Edition compilation failed; check server logs."}
            )
            import logging

            logging.getLogger(__name__).exception("Edition compilation failed for %s", user_id)
    return {"checked": len(ids), "compiled": len(compiled), "failed": failed}
