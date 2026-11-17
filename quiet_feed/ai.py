import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .content import plain_text
from .models import (
    MODELS,
    Article,
    Edition,
    EditionArticle,
    EditionSummary,
    Feed,
    UserSettings,
    identifier,
    now,
)
from .security import decrypt_secret

log = logging.getLogger(__name__)
API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


def validate_key(key):
    try:
        response = httpx.get(
            f"{API_ROOT}/models", headers={"x-goog-api-key": key.strip()}, timeout=10
        )
        if response.is_success:
            return
        raise ValueError(
            "Google rejected the API key. Check that it is valid and has Gemini API access."
        )
    except httpx.RequestError as error:
        raise ValueError(
            "Could not reach Google to validate the API key. Try again shortly."
        ) from error


def generate_digest(key, model, stories, edition):
    if not stories:
        return {
            "markdown": "_None of your subscribed feeds had new stories in this edition._",
            "model": model,
            "prompt": 0,
            "completion": 0,
        }
    distilled = []
    for progress, article, feed in stories:
        lead = plain_text(article.excerpt or article.content_html)[:1000]
        distilled.append(
            f"[Article ID: {progress.id}]\nTitle: {article.title}\nSource: {feed.title} ({feed.category})\nLead: {lead or '(No excerpt available)'}"
        )
    prompt = f"""You are the executive editor for Quiet Feed, a calm, distraction-free daily news publication.
Write The Morning Dispatch for Issue №{edition.issue_number} · {edition.date}.
Use restrained, intelligent, clear, objective prose. Avoid clickbait and AI fluff.
Synthesize related stories thematically, in roughly 600 to 1,200 words total.
Whenever mentioning a specific article, link to its exact supplied Article ID:
[Article Headline](/article/{{Article ID}}). Never invent IDs or links.
Structure:
### The Lead
A 2–3 sentence synthesis of the most important theme.
### Key Themes & Developments
Group stories into 3–5 themes, with narrative paragraphs and article links.
### Noted in Brief
3–5 brief noteworthy items.

Stories:
""" + "\n\n---\n\n".join(distilled)
    last_error = "Gemini could not generate a dispatch."
    candidates = list(dict.fromkeys([model, *MODELS]))
    with httpx.Client(timeout=60) as client:
        for candidate in candidates:
            try:
                response = client.post(
                    f"{API_ROOT}/models/{candidate}:generateContent",
                    headers={"x-goog-api-key": key.strip()},
                    json={
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.3,
                            "maxOutputTokens": 8192,
                            "thinkingConfig": {"thinkingBudget": 0},
                        },
                    },
                )
                if response.status_code in {401, 403}:
                    raise ValueError("Google rejected the saved API key. Check it in Settings.")
                if not response.is_success:
                    last_error = (
                        f"Gemini request failed (HTTP {response.status_code}, {candidate})."
                    )
                    continue
                data = response.json()
                text = "".join(
                    part.get("text", "")
                    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                )
                if not text.strip():
                    last_error = f"Gemini returned an empty response ({candidate})."
                    continue
                usage = data.get("usageMetadata", {})
                return {
                    "markdown": text.strip(),
                    "model": candidate,
                    "prompt": usage.get("promptTokenCount", 0),
                    "completion": usage.get("candidatesTokenCount", 0),
                }
            except (httpx.RequestError, KeyError, IndexError) as error:
                last_error = f"Could not complete the Gemini request ({type(error).__name__})."
    raise ValueError(last_error)


class DispatchJobs:
    """Bounded, single-process jobs; persisted claims prevent duplicate paid requests."""

    def __init__(self, database, config):
        self.database, self.config = database, config
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dispatch")
        self.pending = set()
        self.lock = Lock()

    def start(self, edition_id, user_id, force=False):
        with self.lock:
            if edition_id in self.pending:
                return
            with self.database.transaction() as session:
                edition = session.scalar(
                    select(Edition).where(Edition.id == edition_id, Edition.user_id == user_id)
                )
                settings = session.get(UserSettings, user_id)
                if not edition or not settings or not settings.gemini_api_key:
                    raise ValueError("Configure a Gemini API key in Settings first.")
                if not decrypt_secret(settings.gemini_api_key, self.config):
                    raise ValueError(
                        "Could not decrypt the saved Gemini key. Keep your original encryption secret."
                    )
                existing = session.scalar(
                    select(EditionSummary).where(EditionSummary.edition_id == edition_id)
                )
                if existing and existing.status == "completed" and not force:
                    return
                if (
                    existing
                    and existing.status == "generating"
                    and existing.created_at > now() - 600
                ):
                    return
                if existing:
                    session.execute(
                        update(EditionSummary)
                        .where(EditionSummary.id == existing.id)
                        .values(status="generating", error_message=None, created_at=now())
                    )
                else:
                    session.add(
                        EditionSummary(
                            id=identifier(),
                            edition_id=edition_id,
                            content_markdown="",
                            model=settings.ai_model,
                            status="generating",
                        )
                    )
            self.pending.add(edition_id)
            try:
                self.executor.submit(self._run, edition_id, user_id)
            except Exception:
                self.pending.discard(edition_id)
                raise

    def _run(self, edition_id, user_id):
        try:
            with self.database.transaction() as session:
                settings = session.get(UserSettings, user_id)
                edition = session.get(Edition, edition_id)
                key = decrypt_secret(settings.gemini_api_key, self.config)
                stories = session.execute(
                    select(EditionArticle, Article, Feed)
                    .join(Article, EditionArticle.article_id == Article.id)
                    .join(Feed, Article.feed_id == Feed.id)
                    .where(EditionArticle.edition_id == edition_id)
                    .order_by(EditionArticle.position)
                ).all()
            result = generate_digest(key, settings.ai_model, stories, edition)
            with self.database.transaction() as session:
                session.execute(
                    update(EditionSummary)
                    .where(EditionSummary.edition_id == edition_id)
                    .values(
                        content_markdown=result["markdown"],
                        model=result["model"],
                        prompt_tokens=result["prompt"],
                        completion_tokens=result["completion"],
                        status="completed",
                        error_message=None,
                    )
                )
        except Exception as error:
            with self.database.transaction() as session:
                session.execute(
                    update(EditionSummary)
                    .where(EditionSummary.edition_id == edition_id)
                    .values(
                        status="failed",
                        error_message=str(error)[:500],
                    )
                )
        finally:
            with self.lock:
                self.pending.discard(edition_id)

    def start_automatic(self):
        with self.database.transaction() as session:
            rows = session.execute(
                select(Edition.id, Edition.user_id)
                .join(UserSettings, Edition.user_id == UserSettings.user_id)
                .outerjoin(EditionSummary, EditionSummary.edition_id == Edition.id)
                .where(
                    UserSettings.ai_digest_enabled.is_(True),
                    UserSettings.ai_digest_trigger == "auto",
                    UserSettings.gemini_api_key.is_not(None),
                    EditionSummary.id.is_(None),
                    Edition.created_at >= now() - 86400,
                )
            ).all()
        for edition_id, user_id in rows:
            try:
                self.start(edition_id, user_id)
            except (ValueError, IntegrityError):
                log.warning("Could not start automatic dispatch for edition %s", edition_id)

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=False)
