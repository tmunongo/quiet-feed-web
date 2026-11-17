# Quiet Feed

One frozen daily edition of your feeds. No infinite scroll, badges, or catch-up requirement.

Quiet Feed runs on **FastAPI, Jinja2, HTMX, Alpine.js, SQLAlchemy, and SQLite**.
Python dependencies and Python itself are managed with **uv**. Scripts, styles, and
fonts are served locally; no Node, Bun, frontend build, or runtime CDN is required.

## Upgrading an existing SvelteKit installation

The Python release uses the **same Docker image repository, port 3000, SQLite file,
data volume, and environment variables**. Keep your existing Compose file and secrets.
Once the Python release is published, update the service as usual:

```bash
docker compose pull quiet-feed
docker compose up -d quiet-feed
```

`quiet-feed` is the Compose service name; the `:latest` image tag belongs in the
Compose file. Pulling alone does not replace a running container.

At first startup, the app verifies the Drizzle migration checksums and schema,
creates a consistent SQLite backup under `/app/data/backups/`, adopts the matching
Alembic revision, and applies any pending migrations. Upgrades from all three
original Drizzle revisions and the historical Gemini 2.0 default are supported. Unknown schemas fail startup without
altering application data. Later starts are idempotent.

Your accounts, passwords, subscriptions, articles, archived editions, issue numbers,
closed editions, reading positions, settings, and Gemini keys are retained.
**Sign in once with your existing password** after upgrading.

- Keep `BETTER_AUTH_SECRET` unchanged. Saved Gemini keys use this secret for encryption.
- If you previously set `ENCRYPTION_KEY`, keep that value too.
- Keep the same Compose project/service and volume mount; changing the project name
  can select a different, empty named volume.
- On an HTTP-only Raspberry Pi, keep `SECURE_COOKIES=false`. Use `true` with HTTPS.
- Do not run the old and new applications against the same database simultaneously.

PWA installation and offline reading are deferred. The original `/sw.js` retires
old Workbox caches so browsers do not keep serving Svelte pages. A later release
can add install/offline support without changing the server architecture.

### Rollback

Before updating, record the running image ID and image digest:

```bash
docker inspect quiet-feed --format '{{.Image}}'
docker image inspect ghcr.io/tmunongo/quiet-feed-web:latest --format '{{json .RepoDigests}}'
```

Keep that image available. The migration retains the original application schema,
password format, and Drizzle history; the previous image can reopen the database
without dropping the Alembic tracking table. Change `image:` in your Compose file
to the recorded digest, stop the Python container, and recreate the service.
You will need to sign in again.

If a database restore is necessary, stop the service first. Preserve the current
database and its `-wal`/`-shm` files, then restore the selected backup as
`quiet-feed.db` in the same volume with no old WAL/SHM files alongside it. Start
the pinned previous image. A backup restore discards changes made after that
backup. Do not use `docker compose down -v`; that removes persistent volumes.

## Local development with uv

```bash
uv sync --locked
cp .env.example .env
# Edit .env: set BETTER_AUTH_SECRET to a stable random secret of at least 32 characters.
# For a NEW installation: openssl rand -hex 32
uv run python -m quiet_feed
```

The server runs at `http://localhost:3000`. Migrations run automatically before
serving requests. To apply migrations separately:

```bash
uv run python -m quiet_feed.migrate
```

The checked-in `.python-version` selects Python 3.12; uv downloads it when needed.
Do not replace an existing `.env` or regenerate its secrets when upgrading.

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

For browser regression checks:

```bash
uv run playwright install chromium
uv run python scripts/browser_smoke.py
# Or use an already installed Chrome, with a fresh isolated test profile:
QUIET_FEED_BROWSER_CHANNEL=chrome uv run python scripts/browser_smoke.py
```

The browser script uses a temporary database and a local synthetic feed. Screenshots
are written to ignored `test-results/`. Tests never use your account, real feeds,
Google API, or production database.

## Docker

The published image remains `ghcr.io/tmunongo/quiet-feed-web:latest`, with
`linux/arm64` (64-bit Raspberry Pi) and `linux/amd64` builds.

For a new HTTP-only installation:

```yaml
services:
  quiet-feed:
    image: ghcr.io/tmunongo/quiet-feed-web:latest
    container_name: quiet-feed
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      ORIGIN: http://raspberrypi.local:3000
      BETTER_AUTH_SECRET: "replace-with-a-random-secret-of-at-least-32-characters"
      SECURE_COOKIES: "false"
      ENABLE_INTERNAL_SCHEDULER: "true"
      DATABASE_PATH: /app/data/quiet-feed.db
    volumes:
      - quiet-feed-data:/app/data
    stop_grace_period: 5m
volumes:
  quiet-feed-data:
```

Set `ORIGIN` to the exact address used in your browser. For HTTPS, set the HTTPS
origin and `SECURE_COOKIES=true`. The repository's `compose.yml` also supports
building from source and retains its original Traefik routing/network setup:

```bash
docker compose up -d --build
```

`GET /healthz` checks startup/database availability. The image includes a health
check. One Uvicorn worker owns the scheduler and dispatch jobs. SQLite uses WAL,
foreign keys, and a busy timeout; edition selection/publication is transactional.

### Configuration

See `.env.example`. Existing variables remain accepted:

| Variable | Purpose |
| --- | --- |
| `DATABASE_PATH` | Existing SQLite file; default `./data/quiet-feed.db` |
| `BETTER_AUTH_SECRET` | Stable application secret and default encryption secret |
| `ENCRYPTION_KEY` | Optional existing override for Gemini-key encryption |
| `ORIGIN` | Public origin used for form submission checks |
| `BETTER_AUTH_URL` | Fallback when `ORIGIN` is unset |
| `SECURE_COOKIES` | `false` on HTTP; `true` on HTTPS |
| `ENABLE_INTERNAL_SCHEDULER` | Check for due editions every ten minutes |
| `CRON_SECRET` | Bearer secret for external compilation requests |
| `HOST`, `PORT` | Bind address and port |
| `FORWARDED_ALLOW_IPS` | Trusted reverse proxy IPs/CIDRs for Uvicorn |

Legacy Bun proxy-header variables may remain in old Compose files, but Python
does not use them. If proxy-derived client addresses are needed, explicitly set
`FORWARDED_ALLOW_IPS` to the proxy's IP or network.

## Daily editions

The scheduler checks each user's edition time in their configured IANA timezone.
Opening the home page also compiles a due edition if one is missing, including
after downtime. External scheduling remains available:

```text
POST /api/cron/compile
Authorization: Bearer <CRON_SECRET>
```

An edition contains at most 20 articles by default (configurable from 1–100).
Selection takes one story per source per round, rotates the starting source,
respects per-feed caps, and never repeats an article from a previous edition.
Changing a limit never changes an existing edition.

Closing an edition does not mark its articles read. The archive keeps everything
available without completion counts. The reader saves progress and restores its
position. Feed ingestion respects ETag/Last-Modified, keeps existing GUIDs, and
sanitizes third-party HTML. OPML import/export lives under `/feeds`.

Gemini dispatches retain manual/automatic generation, model fallback, token counts,
and archived summaries. Jobs run in the application process, with persisted claims,
HTMX polling, and retry after interrupted generation. No queue service is needed.

## Project structure

```text
quiet_feed/
  app.py, routes.py      HTTP routes, sessions, CSRF, lifespan and scheduler
  models.py, db.py       SQLAlchemy mappings to the original SQLite schema
  migrate.py            Verified Drizzle adoption, backups and Alembic upgrades
  editions.py           Frozen edition compilation and views
  feeds.py, content.py  Feed ingestion, sanitization, OPML and dispatch rendering
  ai.py, security.py    Gemini jobs, password and encryption compatibility
templates/              Jinja2 pages and HTMX fragments
static/                 Plain CSS, small browser scripts, vendored libraries/fonts
migrations/             Alembic revisions
drizzle/                Immutable original SQL/history required for upgrades
tests/                  Isolated regression and upgrade tests
scripts/                Browser/container smoke checks
```

For future schema changes, edit the SQLAlchemy models and create/review an Alembic
revision (`uv run alembic revision --autogenerate -m "description"`). Do not modify
files under `drizzle/`, `migrations/legacy/`, or the three compatibility revisions: deployed
Drizzle checksums depend on their original contents. All production upgrades run
through `quiet_feed.migrate` so they receive a backup before pending migrations.

CI runs Python checks, browser behavior checks, and an ARM64 container rehearsal
covering fresh installation and every Drizzle revision. A tagged release runs the
Python checks before publishing the existing multi-architecture image and `latest`.
Use `uv version --bump patch` (or `minor`/`major`) to update the project and lockfile,
commit the change, then create the corresponding `vX.Y.Z` tag when ready to release.

See `DESIGN.md` for the visual design rationale.
