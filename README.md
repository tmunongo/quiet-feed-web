# Quiet Feed

A full-stack RSS/Atom reader built around a single frozen daily "Edition" instead of an
infinite, badge-driven feed. SvelteKit + Bun + SQLite (via `bun:sqlite`/Drizzle) + Better
Auth, packaged as an installable PWA for offline reading of whatever edition you've already
opened.

This is a hosted service, not a local-only app: feed fetching, the daily compile job, and
auth all live on the server. The PWA layer is for installability and offline reading, not
for client-side fetching (most RSS hosts don't send CORS headers, so client-side fetching
of arbitrary feeds isn't reliably possible from a browser anyway).

## Stack

- **Runtime:** [Bun](https://bun.sh) — also used for the SQLite driver (`bun:sqlite`), no
  native module compilation step needed.
- **Framework:** SvelteKit 2 (Svelte 5), `svelte-adapter-bun`.
- **Database:** SQLite via Drizzle ORM. Swappable to libSQL/Turso later without touching
  application code, since it's all behind Drizzle's query builder.
- **Auth:** [Better Auth](https://www.better-auth.com), email/password, Drizzle adapter.
- **Styling:** Tailwind CSS v4 (CSS-first `@theme` config, see `src/app.css`).
- **PWA:** `@vite-pwa/sveltekit` — installable, offline fallback for already-visited pages.

## Local development

Requires Bun installed (`curl -fsSL https://bun.sh/install | bash`).

```bash
bun install
cp .env.example .env        # then edit BETTER_AUTH_SECRET at minimum
bun run db:generate         # only needed after schema changes
bun run db:migrate          # creates ./data/quiet-feed.db and applies schema
bun run dev                 # http://localhost:5173
```

Generate a real secret instead of leaving the placeholder:

```bash
openssl rand -hex 32        # use for BETTER_AUTH_SECRET and CRON_SECRET
```

## Building / running in production

```bash
bun run build
bun run db:migrate          # idempotent — safe to run on every deploy
bun run start               # runs build/index.js with svelte-adapter-bun
```

Note the `dev`/`build`/`preview` scripts explicitly call `bun --bun vite ...` rather than
plain `vite ...`. Without the `--bun` flag, Vite's own module resolver doesn't know how to
resolve `bun:sqlite`-style imports (it falls back to Node-compatible resolution); the
`--bun` flag forces Vite itself to run under Bun's runtime so those imports resolve
correctly. This is a known Bun/Vite interaction, not a workaround specific to this project.

### Environment variables

See `.env.example` for the full list with comments. The ones that actually need changing
for a real deployment:

- `BETTER_AUTH_SECRET` — random secret, required.
- `BETTER_AUTH_URL` and `ORIGIN` — both should be the externally reachable URL of the
  deployment (protocol + host). If these are wrong, form submissions (login, settings,
  adding feeds) fail same-origin checks.
- `CRON_SECRET` — only needed if you disable `ENABLE_INTERNAL_SCHEDULER` and point an
  external cron job at `/api/cron/compile` instead (see below).
- `SECURE_COOKIES` — set to `true` once served over HTTPS.

### Self-Hosting with Docker Compose (Pre-built Image)

You can run Quiet Feed using the pre-built Docker image hosted on the GitHub Container Registry (GHCR).

Here is a template `compose.yml` for self-hosting. It mounts a volume for database persistence, starts the SvelteKit app on port 3000, and enables the internal scheduler for processing feeds.

Create a `compose.yml` file:

```yaml
services:
  quiet-feed:
    image: ghcr.io/tmunongo/quiet-feed-web:latest # Replace with your package image path
    container_name: quiet-feed
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      HOST: 0.0.0.0
      PORT: 3000
      # Change these to your actual domain
      ORIGIN: https://quiet-feed.example.com
      BETTER_AUTH_URL: https://quiet-feed.example.com
      # Security settings
      SECURE_COOKIES: "true"
      # Generate random hex strings for these (e.g. openssl rand -hex 32)
      BETTER_AUTH_SECRET: "your-better-auth-secret-here"
      CRON_SECRET: "your-cron-secret-here"
      # Enable internal cron scheduler
      ENABLE_INTERNAL_SCHEDULER: "true"
      DATABASE_PATH: /app/data/quiet-feed.db
    volumes:
      - quiet-feed-data:/app/data

volumes:
  quiet-feed-data:
```

To start the service:
```bash
docker compose up -d
```

---

### Docker / local container build (Development/Homelab)

If you prefer to build the container from source, a `Dockerfile` and `compose.yml` are included in this repo (pre-configured for a Traefik-fronted reverse proxy).

1. Edit the domains in the environment variables and the Traefik labels in `compose.yml`.
2. Generate your secrets:
   ```bash
   export BETTER_AUTH_SECRET=$(openssl rand -hex 32)
   export CRON_SECRET=$(openssl rand -hex 32)
   ```
3. Run the container:
   ```bash
   docker compose up -d --build
   ```

The SQLite database file is persisted in a named volume (`quiet-feed-data`). Migrations run automatically on container start.

If you aren't using Traefik, you can modify `compose.yml` to remove the `labels` and `networks` blocks and expose port 3000 directly:
```yaml
    ports:
      - "3000:3000"
```

## How the daily edition actually gets compiled

Two mechanisms, deliberately redundant:

1. **In-process scheduler** (`src/lib/server/scheduler.ts`) — checks every 10 minutes
   whether each user's configured edition time has passed in their timezone, and compiles
   if so. Controlled by `ENABLE_INTERNAL_SCHEDULER`. Fine for a single server instance.
2. **On-open fallback** (`getOrCompileTodaysEdition` in `src/lib/server/edition/compiler.ts`)
   — checked every time the home page loads. If the edition time has passed and today's
   edition doesn't exist yet, it compiles right then. This is what guarantees an edition
   shows up the moment someone opens the app, even if the scheduler was disabled, the
   server was down at the scheduled time, or you're running multiple instances behind a
   load balancer with the scheduler turned off everywhere.

If you'd rather drive compilation from outside the app (systemd timer, cron, a cloud
scheduler), turn off `ENABLE_INTERNAL_SCHEDULER` and point something at:

```
POST /api/cron/compile
Authorization: Bearer <CRON_SECRET>
```

## Feed fetching notes

- ETag / Last-Modified are respected — a feed that hasn't changed returns 304 and costs
  nothing.
- Feed HTML content is sanitized server-side at ingestion time (`src/lib/server/sanitize.ts`,
  via `sanitize-html`) before ever being stored or rendered with `{@html ...}`. Feed content
  is third-party HTML and shouldn't be trusted by default.
- Articles that have already appeared in any past edition never appear again — the per-feed
  article cap applies to the never-yet-shown backlog, not to the feed's raw item count.
- OPML import/export lives under `/feeds` (import) and `/feeds/export` (export), using a
  minimal parser/serializer in `src/lib/server/feeds/opml.ts` — round-trips with Feedly,
  NetNewsWire, Inoreader, and similar.

## Project structure

```
src/lib/server/
  auth.ts                  Better Auth instance + databaseHooks (auto-provisions
                            a userSettings row on signup)
  db/schema.ts              Drizzle schema — Better Auth tables + app tables
  db/user-settings.ts       Self-healing settings lookup (creates a default row
                            if one is ever missing, rather than throwing)
  edition/compiler.ts        The core "freeze into an Edition" logic
  edition/view.ts            Assembles a frozen edition into the UI's shape
  feeds/fetcher.ts            RSS/Atom fetching, ETag caching, sanitization
  feeds/opml.ts                OPML import/export
  scheduler.ts               In-process compile-when-due loop

src/routes/
  /                          Today's edition (or the empty/closed states)
  /article/[id]              Reader, with scroll-progress persistence
  /feeds                     Subscription management, OPML import/export
  /settings                  Edition time, timezone, theme, habits mode
  /archive, /archive/[date]   Past editions, read-only
  /api/cron/compile           External-cron-friendly compile trigger
```

See `DESIGN.md` for the visual design rationale.

