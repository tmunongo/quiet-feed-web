import asyncio
import hmac
import html
import json
import re
import secrets
from datetime import datetime
from urllib.parse import urlencode
from xml.etree.ElementTree import ParseError
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from defusedxml.common import DefusedXmlException
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from . import ai, editions, feeds
from .app import SESSION_AGE, SESSION_COOKIE, current_user, redirect, render
from .config import ROOT
from .content import build_opml, parse_opml, sanitize_html
from .db import get_settings
from .models import (
    MODELS,
    Account,
    Article,
    Edition,
    EditionArticle,
    Feed,
    LoginSession,
    User,
    identifier,
    now,
)
from .security import decrypt_secret, encrypt_secret, hash_password, mask_key, sign, verify_password

router = APIRouter()
STARTERS = [
    ("https://hnrss.org/frontpage", "Technology"),
    ("https://feeds.arstechnica.com/arstechnica/index", "Technology"),
    ("https://www.theguardian.com/world/rss", "News"),
    ("https://www.nasa.gov/feed/", "Science"),
]


@router.get("/healthz")
def health(request: Request):
    with request.app.state.database.engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")
    return {"status": "ok", "version": request.app.state.config.version}


@router.get("/login", response_class=HTMLResponse)
@router.get("/register", response_class=HTMLResponse)
def auth_page(request: Request):
    if request.state.user:
        return redirect("/", request)
    return render(request, "auth.html", register=request.url.path == "/register")


def authenticate_form(request, form, register):
    email = str(form.get("email", "")).strip().lower()
    password = str(form.get("password", ""))
    name = str(form.get("name", "")).strip()
    try:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
            raise ValueError("Enter a valid email address.")
        if not 8 <= len(password) <= 128:
            raise ValueError("Passwords must contain between 8 and 128 characters.")
        with request.app.state.database.transaction() as session:
            user = session.scalar(select(User).where(func.lower(User.email) == email))
            if register:
                if not name or len(name) > 120:
                    raise ValueError("Enter your name (up to 120 characters).")
                if user:
                    raise ValueError(
                        "Could not create an account with these details. Try signing in."
                    )
                user = User(id=identifier(), name=name, email=email)
                session.add(user)
                session.flush()
                session.add(
                    Account(
                        user_id=user.id,
                        account_id=user.id,
                        provider_id="credential",
                        password=hash_password(password),
                    )
                )
                get_settings(session, user.id)
            else:
                account = (
                    session.scalar(
                        select(Account).where(
                            Account.user_id == user.id, Account.provider_id == "credential"
                        )
                    )
                    if user
                    else None
                )
                # Spend the same work for unknown users and incorrect passwords.
                stored = (
                    account.password if account and account.password else "0" * 32 + ":" + "0" * 128
                )
                if not verify_password(password, stored) or not user:
                    raise ValueError("Email or password is incorrect.")
            token = secrets.token_urlsafe(32)
            session.add(
                LoginSession(
                    token=token,
                    user_id=user.id,
                    expires_at=now() + SESSION_AGE,
                    user_agent=request.headers.get("user-agent", "")[:500],
                )
            )
        response = redirect("/", request)
        request.state.session_changed = True
        response.set_cookie(
            SESSION_COOKIE,
            sign(token, request.app.state.config.secret),
            httponly=True,
            secure=request.app.state.config.secure_cookies,
            samesite="lax",
            max_age=SESSION_AGE,
        )
        return response
    except (ValueError, IntegrityError) as error:
        message = (
            str(error)
            if isinstance(error, ValueError)
            else "Could not create an account with these details."
        )
        return render(
            request,
            "auth.html",
            register=register,
            message=message,
            email=email,
            name=name,
            status_code=400,
        )


@router.post("/login", response_class=HTMLResponse)
@router.post("/register", response_class=HTMLResponse)
async def auth_submit(request: Request):
    request.app.state.limiter.check(request.client.host if request.client else "unknown")
    form = await request.form()
    return await asyncio.to_thread(
        authenticate_form, request, form, request.url.path == "/register"
    )


@router.post("/logout")
def logout(request: Request, user=Depends(current_user)):
    from .security import unsign

    token = unsign(request.cookies.get(SESSION_COOKIE), request.app.state.config.secret)
    with request.app.state.database.transaction() as session:
        session.execute(delete(LoginSession).where(LoginSession.token == token))
    request.state.session_changed = True
    response = redirect("/login", request)
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/", response_class=HTMLResponse)
def home(request: Request, user=Depends(current_user)):
    database = request.app.state.database
    with database.transaction() as session:
        settings = get_settings(session, user.id)
        count = session.scalar(
            select(func.count()).select_from(Feed).where(Feed.user_id == user.id)
        )
    edition = editions.get_or_compile(database, user.id) if count else None
    if edition:
        request.app.state.jobs.start_automatic()
    view = editions.edition_view(database, edition.id, user.id) if edition else None
    return render(
        request,
        "edition.html",
        view=view,
        feed_count=count,
        archive=False,
        settings=settings,
        collapsed=json.loads(settings.collapsed_categories),
    )


@router.post("/edition/fetch")
def fetch_now(request: Request, user=Depends(current_user)):
    if editions.todays_edition(request.app.state.database, user.id):
        raise HTTPException(409, "Today's edition is already sealed.")
    editions.compile_edition(request.app.state.database, user.id)
    request.app.state.jobs.start_automatic()
    return redirect("/", request)


@router.post("/edition/{edition_id}/close")
def close_edition(edition_id: str, request: Request, user=Depends(current_user)):
    with request.app.state.database.transaction() as session:
        edition = session.scalar(
            select(Edition).where(Edition.id == edition_id, Edition.user_id == user.id)
        )
        if not edition:
            raise HTTPException(404, "Edition not found.")
        edition.closed_at = now()
    return redirect("/", request)


@router.get("/archive", response_class=HTMLResponse)
def archive(request: Request, user=Depends(current_user)):
    with request.app.state.database.transaction() as session:
        issues = list(
            session.scalars(
                select(Edition).where(Edition.user_id == user.id).order_by(Edition.date.desc())
            )
        )
    return render(request, "archive.html", issues=issues)


def edition_by_date(database, user_id, date):
    try:
        if datetime.strptime(date, "%Y-%m-%d").date().isoformat() != date:
            raise ValueError()
    except ValueError:
        raise HTTPException(404, "Edition not found.") from None
    with database.transaction() as session:
        edition = session.scalar(
            select(Edition).where(Edition.user_id == user_id, Edition.date == date)
        )
    if not edition:
        raise HTTPException(404, "Edition not found.")
    return edition


@router.get("/archive/{date}", response_class=HTMLResponse)
def archive_edition(date: str, request: Request, user=Depends(current_user)):
    edition = edition_by_date(request.app.state.database, user.id, date)
    return render(
        request,
        "edition.html",
        view=editions.edition_view(request.app.state.database, edition.id, user.id),
        archive=True,
        collapsed=[],
    )


@router.get("/archive/{date}/dispatch")
def archive_dispatch(date: str, request: Request, user=Depends(current_user)):
    edition_by_date(request.app.state.database, user.id, date)
    return redirect(f"/dispatch?date={date}", request)


@router.get("/article/{article_id}", response_class=HTMLResponse)
def article_page(article_id: str, request: Request, user=Depends(current_user)):
    with request.app.state.database.transaction() as session:
        row = session.execute(
            select(EditionArticle, Article, Feed, Edition)
            .join(Article, EditionArticle.article_id == Article.id)
            .join(Feed, Article.feed_id == Feed.id)
            .join(Edition, EditionArticle.edition_id == Edition.id)
            .where(EditionArticle.id == article_id, Edition.user_id == user.id)
        ).first()
        if not row:
            raise HTTPException(404, "Article not found.")
        latest = session.scalar(
            select(Edition.date)
            .where(Edition.user_id == user.id)
            .order_by(Edition.date.desc())
            .limit(1)
        )
    progress, article, feed, edition = row
    back = "/" if edition.date == latest and not edition.closed_at else f"/archive/{edition.date}"
    return render(
        request,
        "article.html",
        progress=progress,
        article=article,
        feed=feed,
        edition=edition,
        back_url=back,
        content=sanitize_html(article.content_html),
    )


class ProgressPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    scrollPercent: float | None = None
    scrollOffset: float | None = None
    read: bool | None = None


@router.post("/article/{article_id}/progress")
def save_progress(
    article_id: str, payload: ProgressPayload, request: Request, user=Depends(current_user)
):
    with request.app.state.database.transaction() as session:
        row = session.scalar(
            select(EditionArticle)
            .join(Edition, EditionArticle.edition_id == Edition.id)
            .where(EditionArticle.id == article_id, Edition.user_id == user.id)
        )
        if row is None:
            raise HTTPException(404, "Article not found.")
        if payload.scrollPercent is not None:
            row.scroll_percent = max(0, min(100, int(payload.scrollPercent + 0.5)))
        if payload.scrollOffset is not None:
            row.scroll_offset = max(0, int(payload.scrollOffset + 0.5))
        if payload.read is not None:
            row.read = payload.read
        row.updated_at = now()
    return {"ok": True}


class CollapsedPayload(BaseModel):
    collapsed: list[str] = Field(max_length=1000)


@router.post("/api/settings/collapsed-categories")
def collapsed_categories(payload: CollapsedPayload, request: Request, user=Depends(current_user)):
    with request.app.state.database.transaction() as session:
        get_settings(session, user.id).collapsed_categories = json.dumps(payload.collapsed)
    return {"ok": True}


@router.get("/feeds", response_class=HTMLResponse)
def feed_page(
    request: Request, user=Depends(current_user), message: str | None = None, error: bool = False
):
    if request.method == "POST" and request.headers.get("hx-request") != "true":
        return redirect(
            "/feeds?" + urlencode({"message": message or "", "error": str(error).lower()}), request
        )
    with request.app.state.database.transaction() as session:
        subscriptions = list(
            session.scalars(
                select(Feed)
                .where(Feed.user_id == user.id)
                .order_by(Feed.category, Feed.position, Feed.created_at)
            )
        )
    return render(request, "feeds.html", feeds=subscriptions, message=message, error=error)


@router.get("/feeds/export")
def export_feeds(request: Request, user=Depends(current_user)):
    with request.app.state.database.transaction() as session:
        subscriptions = list(
            session.scalars(
                select(Feed).where(Feed.user_id == user.id).order_by(Feed.category, Feed.position)
            )
        )
    return Response(
        build_opml(subscriptions),
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="quiet-feed.opml"'},
    )


def manage_feed(request, user, action, form, imported=None):
    database = request.app.state.database
    try:
        if action == "import":
            try:
                parsed = parse_opml(imported)
            except (ParseError, DefusedXmlException):
                raise ValueError("Couldn't read that file as OPML.") from None
            if not parsed:
                raise ValueError("No feeds found in that file.")
            with database.transaction() as session:
                existing = set(session.scalars(select(Feed.url).where(Feed.user_id == user.id)))
                count = 0
                for item in parsed:
                    feeds.validate_url(item["url"])
                    if item["url"] not in existing:
                        session.add(Feed(user_id=user.id, **item))
                        existing.add(item["url"])
                        count += 1
            return feed_page(request, user, message=f"Imported {count} of {len(parsed)} feeds.")
        if action == "starter":
            with database.transaction() as session:
                existing = set(session.scalars(select(Feed.url).where(Feed.user_id == user.id)))
            for url, category in STARTERS:
                if url not in existing:
                    title = feeds.discover_title(url)
                    with database.transaction() as session:
                        session.add(Feed(user_id=user.id, url=url, title=title, category=category))
            return feed_page(request, user, message="Starter feeds added.")
        feed_id = str(form.get("id", ""))
        if action == "delete":
            with database.transaction() as session:
                feed = session.scalar(
                    select(Feed).where(Feed.id == feed_id, Feed.user_id == user.id)
                )
                if not feed:
                    raise HTTPException(404, "Feed not found.")
                session.delete(feed)
            return feed_page(request, user, message="Feed removed.")
        url = feeds.validate_url(str(form.get("url", "")).strip())
        category = str(form.get("category", "General")).strip() or "General"
        title = str(form.get("title", "")).strip()
        cap_value = str(form.get("articleCap", "")).strip()
        cap = int(cap_value) if cap_value else None
        if cap is not None and not 1 <= cap <= 100:
            raise ValueError("The per-feed article cap must be between 1 and 100.")
        if action == "add":
            title = title or feeds.discover_title(url)
            with database.transaction() as session:
                if session.scalar(select(Feed.id).where(Feed.user_id == user.id, Feed.url == url)):
                    raise ValueError("You are already subscribed to that feed.")
                session.add(
                    Feed(user_id=user.id, url=url, title=title, category=category, article_cap=cap)
                )
        elif action == "update":
            if not title:
                raise ValueError("A feed title is required.")
            with database.transaction() as session:
                feed = session.scalar(
                    select(Feed).where(Feed.id == feed_id, Feed.user_id == user.id)
                )
                if not feed:
                    raise HTTPException(404, "Feed not found.")
                feed.url, feed.title, feed.category, feed.article_cap = url, title, category, cap
                feed.etag = feed.last_modified = feed.last_fetch_error = None
            feeds.fetch_feed(database, feed_id)
        else:
            raise HTTPException(404, "Action not found.")
        return feed_page(request, user, message="Feed saved.")
    except ValueError as error:
        return feed_page(request, user, message=str(error), error=True)


@router.post("/feeds/{action}", response_class=HTMLResponse)
async def feed_submit(action: str, request: Request, user=Depends(current_user)):
    form = await request.form()
    imported = None
    if action == "import":
        file = form.get("opml")
        if not hasattr(file, "read"):
            raise HTTPException(400, "Choose an OPML file first.")
        imported = await file.read(2 * 1024 * 1024 + 1)
        if len(imported) > 2 * 1024 * 1024:
            raise HTTPException(400, "OPML files must be smaller than 2 MB.")
    return await asyncio.to_thread(manage_feed, request, user, action, form, imported)


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, user=Depends(current_user), message=None, error=False):
    with request.app.state.database.transaction() as session:
        settings = get_settings(session, user.id)
    key = (
        decrypt_secret(settings.gemini_api_key, request.app.state.config)
        if settings.gemini_api_key
        else None
    )
    return render(
        request,
        "settings.html",
        settings=settings,
        models=list(dict.fromkeys([*MODELS, settings.ai_model])),
        timezones=sorted(available_timezones()),
        masked_key=mask_key(key) if key else None,
        key_error=bool(settings.gemini_api_key and not key),
        message=message,
        error=error,
    )


def update_settings(request, user, form, test=False):
    try:
        with request.app.state.database.transaction() as session:
            settings = get_settings(session, user.id)
        new_key = str(form.get("geminiApiKey", "")).strip()
        if test:
            key = new_key or (
                decrypt_secret(settings.gemini_api_key, request.app.state.config)
                if settings.gemini_api_key
                else None
            )
            if not key:
                raise ValueError("No API key provided, or the saved key could not be decrypted.")
            ai.validate_key(key)
            if request.headers.get("hx-request") == "true":
                return HTMLResponse(
                    '<p class="notice">Google Gemini API key verified successfully.</p>'
                )
            return settings_page(
                request, user, message="Google Gemini API key verified successfully."
            )
        edition_time = str(form.get("editionTime", ""))
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", edition_time):
            raise ValueError("Edition time must be a valid HH:MM time.")
        timezone = str(form.get("timezone", ""))
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Choose a valid timezone.") from None
        theme = str(form.get("theme", ""))
        if theme not in {"system", "light", "dark"}:
            raise ValueError("Choose a valid theme.")
        try:
            default_cap = int(str(form.get("defaultArticleCap", "")))
            edition_cap = int(str(form.get("editionArticleCap", "")))
        except ValueError:
            raise ValueError("Article limits must be whole numbers.") from None
        if not 5 <= default_cap <= 50 or not 1 <= edition_cap <= 100:
            raise ValueError("Per-feed limits must be 5–50 and edition size must be 1–100.")
        model = str(form.get("aiModel", settings.ai_model))
        if model not in {*MODELS, settings.ai_model}:
            raise ValueError("Choose a valid Gemini model.")
        trigger = str(form.get("aiDigestTrigger", "manual"))
        if trigger not in {"manual", "auto"}:
            raise ValueError("Choose a valid digest trigger.")
        encrypted = settings.gemini_api_key
        if form.get("removeGeminiKey"):
            encrypted = None
        elif new_key:
            ai.validate_key(new_key)
            encrypted = encrypt_secret(new_key, request.app.state.config)
        enabled = form.get("aiDigestEnabled") == "on"
        if enabled and not encrypted:
            raise ValueError("A valid Gemini API key is required to enable daily digests.")
        with request.app.state.database.transaction() as session:
            settings = get_settings(session, user.id)
            settings.edition_time, settings.timezone, settings.theme = edition_time, timezone, theme
            settings.default_article_cap, settings.edition_article_cap = default_cap, edition_cap
            settings.habits_mode = form.get("habitsMode") == "on"
            settings.ai_model, settings.ai_digest_trigger = model, trigger
            settings.gemini_api_key, settings.ai_digest_enabled = encrypted, enabled
        return redirect("/settings?saved=1", request)
    except ValueError as error:
        if test and request.headers.get("hx-request") == "true":
            return HTMLResponse(f'<p class="error-message">{html.escape(str(error))}</p>')
        return settings_page(request, user, message=str(error), error=True)


@router.post("/settings", response_class=HTMLResponse)
@router.post("/settings/test-key", response_class=HTMLResponse)
async def settings_submit(request: Request, user=Depends(current_user)):
    form = await request.form()
    return await asyncio.to_thread(
        update_settings, request, user, form, request.url.path.endswith("test-key")
    )


def dispatch_edition(request, user):
    date = request.query_params.get("date")
    edition = (
        edition_by_date(request.app.state.database, user.id, date)
        if date
        else editions.get_or_compile(request.app.state.database, user.id)
    )
    if not edition:
        raise HTTPException(404, "No edition available.")
    return edition


@router.get("/dispatch", response_class=HTMLResponse)
def dispatch_page(request: Request, user=Depends(current_user)):
    edition = dispatch_edition(request, user)
    view = editions.edition_view(request.app.state.database, edition.id, user.id)
    return render(
        request,
        "dispatch.html",
        view=view,
        back_url=f"/archive/{edition.date}" if request.query_params.get("date") else "/",
    )


@router.get("/edition/{edition_id}/summary", response_class=HTMLResponse)
def summary_fragment(edition_id: str, request: Request, user=Depends(current_user)):
    view = editions.edition_view(request.app.state.database, edition_id, user.id)
    if not view:
        raise HTTPException(404, "Edition not found.")
    return render(request, "_summary.html", view=view, full=request.query_params.get("full") == "1")


@router.post("/edition/{edition_id}/summary", response_class=HTMLResponse)
def generate_summary(edition_id: str, request: Request, user=Depends(current_user)):
    if not editions.edition_view(request.app.state.database, edition_id, user.id):
        raise HTTPException(404, "Edition not found.")
    if not request.state.settings.ai_digest_enabled:
        raise HTTPException(400, "Enable AI daily digests in Settings first.")
    try:
        request.app.state.jobs.start(edition_id, user.id, force=True)
    except ValueError as error:
        raise HTTPException(400, str(error)) from None
    if request.headers.get("hx-request") != "true":
        return redirect(
            f"/dispatch?date={editions.edition_view(request.app.state.database, edition_id, user.id)['edition'].date}"
        )
    return summary_fragment(edition_id, request, user)


@router.post("/api/cron/compile")
def cron_compile(request: Request):
    expected = request.app.state.config.cron_secret
    provided = request.headers.get("authorization", "")
    token = re.sub(r"^Bearer\s+", "", provided, flags=re.I)
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(401, "Unauthorized")
    result = editions.compile_due(request.app.state.database)
    request.app.state.jobs.start_automatic()
    return result


@router.get("/sw.js")
def retire_service_worker():
    source = (ROOT / "static/retire-sw.js").read_text()
    return Response(
        source,
        media_type="application/javascript",
        headers={"Cache-Control": "no-store", "Service-Worker-Allowed": "/"},
    )


@router.get("/offline")
def offline():
    return redirect("/")
