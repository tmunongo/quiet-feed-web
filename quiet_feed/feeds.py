import calendar
import logging
from urllib.parse import urlsplit

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from .content import plain_text, sanitize_html
from .models import Article, Feed, identifier, now

log = logging.getLogger(__name__)
HEADERS = {"User-Agent": "QuietFeed/1.0 (+https://github.com/tmunongo/quiet-feed-web)"}
MAX_FEED_BYTES = 10 * 1024 * 1024


def validate_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Use a complete http:// or https:// feed URL.")
    return url


def download_feed(url, headers=None):
    validate_url(url)
    with httpx.Client(timeout=15, follow_redirects=True, headers=HEADERS) as client:
        with client.stream("GET", url, headers=headers or {}) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > MAX_FEED_BYTES:
                    raise ValueError("Feed exceeds the 10 MB size limit.")
            return response.status_code, response.headers, bytes(data)


def parse_feed(data):
    # Disable feedparser's own sanitizer and URI rewriting: preserve original GUIDs
    # and use the same application sanitizer for RSS, Atom and JSON Feed content.
    parsed = feedparser.parse(data, sanitize_html=False, resolve_relative_uris=False)
    if not parsed.version:
        raise ValueError(
            "Could not parse RSS/Atom XML. Double-check that the URL points to a feed."
        )
    return parsed


def discover_title(url):
    try:
        _, _, data = download_feed(url)
        return parse_feed(data).feed.get("title", "").strip() or url
    except Exception:
        return url


def fetch_feed(database, feed_id):
    with database.transaction() as session:
        feed = session.get(Feed, feed_id)
        if feed is None:
            return {"feedId": feed_id, "status": "error", "newArticleCount": 0}
    headers = {}
    if feed.etag:
        headers["If-None-Match"] = feed.etag
    if feed.last_modified:
        headers["If-Modified-Since"] = feed.last_modified
    try:
        status, response_headers, data = download_feed(feed.url, headers)
        parsed = None if status == 304 else parse_feed(data)
        count = 0
        with database.transaction() as session:
            current = session.get(Feed, feed_id)
            if current is None or current.url != feed.url:
                return {"feedId": feed_id, "status": "not-modified", "newArticleCount": 0}
            if parsed:
                for entry in parsed.entries:
                    guid = (
                        entry.get("id") or entry.get("link") or entry.get("title") or identifier()
                    )
                    content = next(
                        (c.get("value") for c in entry.get("content", []) if c.get("value")), None
                    ) or entry.get("summary")
                    published = entry.get("published_parsed") or entry.get("updated_parsed")
                    statement = (
                        insert(Article)
                        .values(
                            id=identifier(),
                            feed_id=feed.id,
                            guid=guid,
                            title=entry.get("title", "").strip() or "(untitled)",
                            url=entry.get("link", ""),
                            author=entry.get("author"),
                            content_html=sanitize_html(content),
                            excerpt=plain_text(entry.get("summary") or content)[:400] or None,
                            published_at=calendar.timegm(published) if published else None,
                            fetched_at=now(),
                        )
                        .on_conflict_do_nothing(index_elements=["feed_id", "guid"])
                    )
                    count += session.execute(statement).rowcount
                current.etag = response_headers.get("etag")
                current.last_modified = response_headers.get("last-modified")
            current.last_fetched_at = now()
            current.last_fetch_error = None
        return {
            "feedId": feed_id,
            "status": "not-modified" if status == 304 else "updated",
            "newArticleCount": count,
        }
    except Exception as error:
        # Do not store request headers (which could contain third-party credentials).
        message = str(error)[:1000] or "Could not fetch feed."
        with database.transaction() as session:
            current = session.get(Feed, feed_id)
            if current is not None and current.url == feed.url:
                current.last_fetched_at, current.last_fetch_error = now(), message
        return {"feedId": feed_id, "status": "error", "newArticleCount": 0, "error": message}


def fetch_all(database, user_id):
    with database.transaction() as session:
        ids = list(session.scalars(select(Feed.id).where(Feed.user_id == user_id)))
    return [fetch_feed(database, feed_id) for feed_id in ids]
