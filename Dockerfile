# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.13.7 AS uv
FROM python:3.12-slim-bookworm AS runtime

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" HOST=0.0.0.0 PORT=3000

COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY quiet_feed ./quiet_feed
COPY templates ./templates
COPY static ./static
COPY migrations ./migrations
COPY drizzle ./drizzle
COPY alembic.ini ./alembic.ini

ARG COMMIT_HASH
ARG APP_VERSION
ENV COMMIT_HASH=${COMMIT_HASH} APP_VERSION=${APP_VERSION}
ENV DATABASE_PATH=/app/data/quiet-feed.db
VOLUME ["/app/data"]
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','3000')+'/healthz',timeout=4)"]
CMD ["python", "-m", "quiet_feed"]
