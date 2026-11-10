# syntax=docker/dockerfile:1
FROM oven/bun:1 AS dependencies
WORKDIR /app

COPY package.json bun.lock ./
RUN --mount=type=cache,target=/root/.bun/install/cache \
    bun install --frozen-lockfile

FROM oven/bun:1 AS production-dependencies
WORKDIR /app
COPY package.json bun.lock ./
# Runtime peers (SvelteKit, Svelte, Drizzle) are explicit dependencies.
# Skip automatically installed peers such as Vite and Drizzle Kit.
RUN --mount=type=cache,target=/root/.bun/install/cache \
    bun install --production --omit=peer --frozen-lockfile

FROM dependencies AS build
COPY . .
# Release metadata changes must not invalidate dependency installation.
ARG COMMIT_HASH
ARG APP_VERSION
ENV COMMIT_HASH=${COMMIT_HASH}
ENV APP_VERSION=${APP_VERSION}
RUN BETTER_AUTH_SECRET=quiet-feed-build-dummy-secret-at-least-32-chars bun --bun vite build

FROM oven/bun:1-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production

ARG COMMIT_HASH
ARG APP_VERSION
ENV COMMIT_HASH=${COMMIT_HASH}
ENV APP_VERSION=${APP_VERSION}

COPY --from=build /app/build ./build
COPY --from=build /app/drizzle ./drizzle
COPY --from=build /app/scripts ./scripts
COPY --from=build /app/package.json ./package.json
COPY --from=production-dependencies /app/node_modules ./node_modules

# Database lives on a volume so it survives image rebuilds/redeploys.
VOLUME ["/app/data"]
ENV DATABASE_PATH=/app/data/quiet-feed.db

EXPOSE 3000
CMD ["sh", "-c", "bun ./scripts/migrate.js && exec bun ./build/index.js"]
