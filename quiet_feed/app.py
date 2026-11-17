import asyncio
import hmac
import logging
import secrets
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from time import monotonic

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, select, update

from .ai import DispatchJobs
from .config import ROOT, Config
from .content import render_dispatch
from .db import Database, get_settings
from .editions import compile_due
from .migrate import migrate
from .models import EditionSummary, LoginSession, User, now
from .security import sign, unsign

log = logging.getLogger(__name__)
SESSION_COOKIE = "quiet_feed_session"
CSRF_COOKIE = "quiet_feed_csrf"
SESSION_AGE = 30 * 86400


def authenticate(database, cookie, config):
    token = unsign(cookie, config.secret)
    if not token:
        return None, None
    with database.transaction() as session:
        login = session.scalar(
            select(LoginSession).where(LoginSession.token == token, LoginSession.expires_at > now())
        )
        if not login:
            return None, None
        if now() - login.updated_at >= 15 * 86400:
            login.expires_at, login.updated_at = now() + SESSION_AGE, now()
        user = session.get(User, login.user_id)
        settings = get_settings(session, user.id)
        return user, settings


async def csrf_check(request: Request):
    if request.method in {"GET", "HEAD", "OPTIONS"} or request.url.path == "/api/cron/compile":
        return
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != request.app.state.config.public_origin:
        raise HTTPException(403, "This form was submitted from a different origin.")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-site submissions are not allowed.")
    provided = request.headers.get("x-csrf-token", "")
    if not provided and "application/x-www-form-urlencoded" in request.headers.get(
        "content-type", ""
    ):
        provided = str((await request.form()).get("csrf_token", ""))
    if not provided and "multipart/form-data" in request.headers.get("content-type", ""):
        provided = str((await request.form()).get("csrf_token", ""))
    expected = request.cookies.get(CSRF_COOKIE, "")
    if (
        not expected
        or not unsign(expected, request.app.state.config.secret)
        or not hmac.compare_digest(provided.encode(), expected.encode())
    ):
        raise HTTPException(403, "This form has expired. Refresh the page and try again.")


def current_user(request: Request):
    if request.state.user is None:
        raise HTTPException(401, "Please sign in.")
    return request.state.user


def redirect(path, request=None):
    # Fetch follows 303s before HTMX sees their headers. Return a 200 for
    # HX-Redirect so changes to theme/auth reload the complete document.
    if request is not None and request.headers.get("hx-request") == "true":
        return Response(headers={"HX-Redirect": path})
    return RedirectResponse(path, status_code=303)


def render(request, template, status_code=200, **context):
    config = request.app.state.config
    context = {
        "user": request.state.user,
        "settings": request.state.settings,
        "csrf_token": request.state.csrf,
        "config": config,
        **context,
    }
    # HTMX requests replace only #main; ordinary requests receive the full document.
    context["partial"] = request.headers.get("hx-request") == "true" and not request.headers.get(
        "hx-history-restore-request"
    )
    return request.app.state.templates.TemplateResponse(
        request=request, name=template, context=context, status_code=status_code
    )


class LoginLimiter:
    def __init__(self):
        self.attempts = defaultdict(deque)

    def check(self, address):
        cutoff = monotonic() - 60
        # Bound memory as well as per-address attempts.
        if len(self.attempts) > 10000:
            self.attempts = defaultdict(
                deque,
                {
                    key: values
                    for key, values in self.attempts.items()
                    if values and values[-1] > cutoff
                },
            )
        queue = self.attempts[address]
        while queue and queue[0] < cutoff:
            queue.popleft()
        if len(queue) >= 10:
            raise HTTPException(429, "Too many sign-in attempts. Please wait a minute.")
        queue.append(monotonic())


def create_app(config=None):
    config = config or Config.from_env()

    @asynccontextmanager
    async def lifespan(app):
        config.validate()
        await asyncio.to_thread(migrate, config.database_path)
        database = Database(config.database_path.resolve())
        app.state.database = database
        app.state.jobs = DispatchJobs(database, config)
        with database.transaction() as session:
            # The previous process cannot still own a job once this single-worker app boots.
            session.execute(
                update(EditionSummary)
                .where(EditionSummary.status == "generating")
                .values(
                    status="failed",
                    error_message="Generation was interrupted by a restart. You can try again.",
                )
            )
            session.execute(delete(LoginSession).where(LoginSession.expires_at < now()))

        stopping = asyncio.Event()

        async def wait_until_stopping(seconds):
            try:
                await asyncio.wait_for(stopping.wait(), timeout=seconds)
            except TimeoutError:
                pass

        async def scheduler():
            await wait_until_stopping(15)
            while not stopping.is_set():
                try:
                    await asyncio.to_thread(compile_due, database)
                    await asyncio.to_thread(app.state.jobs.start_automatic)
                except Exception:
                    log.exception("Scheduler tick failed")
                await wait_until_stopping(600)

        task = asyncio.create_task(scheduler()) if config.scheduler else None
        try:
            yield
        finally:
            if task:
                stopping.set()
                await task
            await asyncio.to_thread(app.state.jobs.close)
            database.close()

    app = FastAPI(
        title="Quiet Feed",
        lifespan=lifespan,
        dependencies=[Depends(csrf_check)],
        docs_url=None,
        redoc_url=None,
    )
    app.state.config = config
    app.state.limiter = LoginLimiter()
    app.state.templates = Jinja2Templates(directory=ROOT / "templates")
    app.state.templates.env.filters["dispatch"] = render_dispatch

    def date_label(value, fmt="%d %b"):
        if not value:
            return ""
        date = (
            datetime.fromtimestamp(value, UTC)
            if isinstance(value, (int, float))
            else datetime.fromisoformat(value)
        )
        return date.strftime(fmt)

    app.state.templates.env.filters["date_label"] = date_label
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    app.mount("/icons", StaticFiles(directory=ROOT / "static/icons"), name="icons")

    @app.middleware("http")
    async def request_context(request, call_next):
        started = monotonic()
        request.state.user, request.state.settings = None, None
        request.state.csrf = request.cookies.get(CSRF_COOKIE, "")
        if not unsign(request.state.csrf, config.secret):
            request.state.csrf = sign(secrets.token_urlsafe(32), config.secret)
        cookie = request.cookies.get(SESSION_COOKIE)
        if cookie and not request.url.path.startswith(("/static/", "/icons/")):
            request.state.user, request.state.settings = await asyncio.to_thread(
                authenticate, app.state.database, cookie, config
            )
        response = await call_next(request)
        if request.cookies.get(CSRF_COOKIE) != request.state.csrf:
            response.set_cookie(
                CSRF_COOKIE,
                request.state.csrf,
                httponly=True,
                secure=config.secure_cookies,
                samesite="lax",
                max_age=SESSION_AGE,
            )
        if request.state.user and cookie and not getattr(request.state, "session_changed", False):
            response.set_cookie(
                SESSION_COOKIE,
                cookie,
                httponly=True,
                secure=config.secure_cookies,
                samesite="lax",
                max_age=SESSION_AGE,
            )
        if not request.url.path.startswith(("/static/", "/icons/")):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Vary"] = "HX-Request, HX-History-Restore-Request, Cookie"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        log.info(
            "%s %s %s %dms",
            request.method,
            request.url.path,
            response.status_code,
            (monotonic() - started) * 1000,
        )
        return response

    @app.exception_handler(HTTPException)
    async def handle_error(request, error):
        is_api = request.url.path.startswith("/api/") or request.url.path.endswith("/progress")
        if error.status_code == 401 and not is_api:
            return redirect("/login", request)
        if is_api:
            return JSONResponse({"detail": error.detail}, status_code=error.status_code)
        return render(request, "error.html", status_code=error.status_code, message=error.detail)

    from .routes import router

    app.include_router(router)
    return app
