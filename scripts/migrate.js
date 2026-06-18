// Applies any pending SQL migrations from ./drizzle to the SQLite database
// at DATABASE_PATH. Run this once after `bun run db:generate` and again
// after pulling schema changes. Run with: bun ./scripts/migrate.js
import { drizzle } from 'drizzle-orm/bun-sqlite';
import { migrate } from 'drizzle-orm/bun-sqlite/migrator';
import { Database } from 'bun:sqlite';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

const DATABASE_PATH = process.env.DATABASE_PATH ?? './data/quiet-feed.db';
mkdirSync(dirname(DATABASE_PATH), { recursive: true });

const sqlite = new Database(DATABASE_PATH);
sqlite.exec('PRAGMA journal_mode = WAL;');
const db = drizzle(sqlite);

migrate(db, { migrationsFolder: './drizzle' });

console.log(`Migrations applied to ${DATABASE_PATH}`);
sqlite.close();
