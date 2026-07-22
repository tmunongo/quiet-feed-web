# syntax=docker/dockerfile:1
FROM oven/bun:1 AS build
WORKDIR /app

ARG COMMIT_HASH
ARG APP_VERSION
ENV COMMIT_HASH=${COMMIT_HASH}
ENV APP_VERSION=${APP_VERSION}

COPY package.json bun.lock* bun.lockb* ./
RUN bun install --frozen-lockfile || bun install

COPY . .
ENV BETTER_AUTH_SECRET=quiet-feed-build-dummy-secret-at-least-32-chars
RUN bun --bun vite build

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
COPY --from=build /app/node_modules ./node_modules

# Database lives on a volume so it survives image rebuilds/redeploys.
VOLUME ["/app/data"]
ENV DATABASE_PATH=/app/data/quiet-feed.db

EXPOSE 3000
CMD ["sh", "-c", "bun ./scripts/migrate.js && bun ./build/index.js"]
