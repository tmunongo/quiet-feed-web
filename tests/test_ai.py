from threading import Event

import httpx
import pytest
from conftest import CRYPTO
from sqlalchemy import select

from quiet_feed import ai, editions
from quiet_feed.models import EditionSummary, UserSettings


def test_digest_fallback_links_and_usage(monkeypatch):
    calls = []

    def handle(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(404, json={"error": {"message": "Model unavailable"}})
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "### The Lead\n\nA dispatch."}]}}],
                "usageMetadata": {"promptTokenCount": 123, "candidatesTokenCount": 45},
            },
        )

    original_client = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs),
    )
    from types import SimpleNamespace

    progress = SimpleNamespace(id="existing-progress-id")
    article = SimpleNamespace(title="Story", excerpt="Lead", content_html="<p>Body</p>")
    feed = SimpleNamespace(title="Source", category="News")
    edition = SimpleNamespace(issue_number=42, date="2025-01-01")
    result = ai.generate_digest(
        "synthetic-key", "missing-model", [(progress, article, feed)], edition
    )
    assert len(calls) == 2
    assert b"existing-progress-id" in calls[0].content
    assert calls[0].headers["x-goog-api-key"] == "synthetic-key"
    assert result["prompt"] == 123 and result["completion"] == 45


def test_digest_auth_failure_does_not_retry_other_models(monkeypatch):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(403, json={"error": {"message": "Forbidden"}})

    original_client = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs),
    )
    from types import SimpleNamespace

    with pytest.raises(ValueError, match="rejected"):
        ai.generate_digest(
            "bad-key",
            "model",
            [
                (
                    SimpleNamespace(id="ea"),
                    SimpleNamespace(title="Story", excerpt="Lead"),
                    SimpleNamespace(title="Source", category="News"),
                )
            ],
            SimpleNamespace(issue_number=1, date="2025-01-01"),
        )
    assert len(calls) == 1


def test_generation_claim_prevents_duplicate_requests_and_saves_result(
    database, config, monkeypatch
):
    edition_id, _ = editions.compile_edition(database, "reader")
    with database.transaction() as session:
        settings = session.get(UserSettings, "reader")
        settings.gemini_api_key = CRYPTO["ciphertext"]
    entered, release = Event(), Event()
    calls = []

    def generate(*args):
        calls.append(args)
        entered.set()
        assert release.wait(5)
        return {"markdown": "Saved dispatch", "model": "test-model", "prompt": 10, "completion": 20}

    monkeypatch.setattr(ai, "generate_digest", generate)
    jobs = ai.DispatchJobs(database, config)
    try:
        jobs.start(edition_id, "reader")
        assert entered.wait(3)
        jobs.start(edition_id, "reader", force=True)
        assert len(calls) == 1
    finally:
        release.set()
        jobs.close()
    with database.transaction() as session:
        summary = session.scalar(select(EditionSummary))
        assert summary.status == "completed"
        assert summary.content_markdown == "Saved dispatch"
        assert summary.prompt_tokens == 10 and summary.completion_tokens == 20


def test_generation_errors_persist_and_allow_retry(database, config, monkeypatch):
    edition_id, _ = editions.compile_edition(database, "reader")
    with database.transaction() as session:
        session.get(UserSettings, "reader").gemini_api_key = CRYPTO["ciphertext"]
    monkeypatch.setattr(
        ai, "generate_digest", lambda *_: (_ for _ in ()).throw(ValueError("Synthetic failure"))
    )
    jobs = ai.DispatchJobs(database, config)
    jobs.start(edition_id, "reader")
    jobs.close()
    with database.transaction() as session:
        summary = session.scalar(select(EditionSummary))
        assert summary.status == "failed" and summary.error_message == "Synthetic failure"
