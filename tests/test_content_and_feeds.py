from types import SimpleNamespace

import pytest
from sqlalchemy import select

from quiet_feed import feeds
from quiet_feed.content import build_opml, parse_opml, render_dispatch, sanitize_html
from quiet_feed.models import Article, Feed


def test_sanitizing_article_html_blocks_scripts_handlers_and_framework_attributes():
    source = '<p class="text">Safe <strong>story</strong></p><script>alert(1)</script><img src="https://example.com/a.png" onerror="alert(1)"><a href="javascript:alert(1)" hx-get="/logout" x-init="alert(1)">link</a><iframe src="https://example.com"></iframe>'
    result = sanitize_html(source)
    assert "<strong>story</strong>" in result
    for forbidden in ["<script", "<iframe", "onerror", "javascript:", "hx-get", "x-init"]:
        assert forbidden not in result
    assert 'rel="noopener noreferrer"' in result


def test_dispatch_only_links_internal_article_ids_and_escapes_html():
    result = str(
        render_dispatch(
            "### The Lead\n\n**Good** [story](/article/ea_123) and [bad](javascript:alert) <script>alert(1)</script>\n\n- One\n- Two"
        )
    )
    assert '<a href="/article/ea_123">story</a>' in result
    assert "<script>" not in result
    assert 'href="javascript:' not in result
    assert "<strong>Good</strong>" in result
    assert "<ul>" in result


def test_opml_nested_categories_and_escaping():
    data = b'<opml version="2.0"><body><outline text="Outer"><outline text="Inner"><outline xmlUrl="https://example.com/rss?a=1&amp;b=2" title="Title &amp; more"/></outline></outline></body></opml>'
    parsed = parse_opml(data)
    assert parsed[0]["category"] == "Inner"
    assert parse_opml(build_opml([SimpleNamespace(**parsed[0])])) == parsed
    with pytest.raises(Exception):
        parse_opml(
            b'<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><opml><body>&secret;</body></opml>'
        )


def test_feed_conditional_requests_keep_guid_and_avoid_duplicates(database, monkeypatch):
    rss = b"""<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>Source</title><link>https://example.com</link><description>Feed</description><item><guid isPermaLink="false">existing-guid</guid><title>Existing</title><link>https://example.com/existing</link></item><item><guid isPermaLink="false">new-guid</guid><title>New story</title><link>https://example.com/new</link><content:encoded><![CDATA[<p>Text</p><script>bad()</script>]]></content:encoded><pubDate>Tue, 10 Mar 2026 10:00:00 GMT</pubDate></item></channel></rss>"""
    with database.transaction() as session:
        session.add(
            Article(
                feed_id="a",
                guid="existing-guid",
                title="Original title",
                url="https://example.com/existing",
            )
        )
        feed = session.get(Feed, "a")
        feed.etag, feed.last_modified = "old-etag", "old-modified"
    calls = []

    def download(url, headers):
        calls.append(headers)
        return 200, {"etag": "new-etag", "last-modified": "new-modified"}, rss

    monkeypatch.setattr(feeds, "download_feed", download)
    assert feeds.fetch_feed(database, "a")["newArticleCount"] == 1
    assert feeds.fetch_feed(database, "a")["newArticleCount"] == 0
    assert calls[0] == {"If-None-Match": "old-etag", "If-Modified-Since": "old-modified"}
    assert calls[1]["If-None-Match"] == "new-etag"
    with database.transaction() as session:
        article = session.scalar(select(Article).where(Article.guid == "existing-guid"))
        assert article.title == "Original title"
        article = session.scalar(select(Article).where(Article.guid == "new-guid"))
        assert "<script>" not in article.content_html
        assert article.published_at == 1773136800
    monkeypatch.setattr(feeds, "download_feed", lambda *_: (304, {}, b""))
    assert feeds.fetch_feed(database, "a")["status"] == "not-modified"


def test_atom_ids_and_html_feed_errors(database, monkeypatch):
    atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom</title><entry><id>urn:article:original</id><title>Atom story</title><link href="https://example.com/atom"/><content type="html">&lt;p&gt;Atom content&lt;/p&gt;</content></entry></feed>'
    monkeypatch.setattr(feeds, "download_feed", lambda *_: (200, {}, atom))
    assert feeds.fetch_feed(database, "a")["newArticleCount"] == 1
    assert feeds.fetch_feed(database, "a")["newArticleCount"] == 0
    monkeypatch.setattr(
        feeds, "download_feed", lambda *_: (200, {}, b"<html><body>Profile page</body></html>")
    )
    assert feeds.fetch_feed(database, "a")["status"] == "error"
