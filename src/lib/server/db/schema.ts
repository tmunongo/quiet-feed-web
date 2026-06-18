import { sqliteTable, text, integer, unique } from 'drizzle-orm/sqlite-core';

// ---------------------------------------------------------------------------
// Better Auth core tables (sqlite shape expected by drizzleAdapter). Keep the
// table names and columns in sync with `bunx @better-auth/cli generate` if
// plugins are added later.
// ---------------------------------------------------------------------------

export const user = sqliteTable('user', {
	id: text('id').primaryKey(),
	name: text('name').notNull(),
	email: text('email').notNull().unique(),
	emailVerified: integer('email_verified', { mode: 'boolean' }).notNull().default(false),
	image: text('image'),
	createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
	updatedAt: integer('updated_at', { mode: 'timestamp' }).notNull()
});

export const session = sqliteTable('session', {
	id: text('id').primaryKey(),
	expiresAt: integer('expires_at', { mode: 'timestamp' }).notNull(),
	token: text('token').notNull().unique(),
	createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
	updatedAt: integer('updated_at', { mode: 'timestamp' }).notNull(),
	ipAddress: text('ip_address'),
	userAgent: text('user_agent'),
	userId: text('user_id')
		.notNull()
		.references(() => user.id, { onDelete: 'cascade' })
});

export const account = sqliteTable('account', {
	id: text('id').primaryKey(),
	accountId: text('account_id').notNull(),
	providerId: text('provider_id').notNull(),
	userId: text('user_id')
		.notNull()
		.references(() => user.id, { onDelete: 'cascade' }),
	accessToken: text('access_token'),
	refreshToken: text('refresh_token'),
	idToken: text('id_token'),
	accessTokenExpiresAt: integer('access_token_expires_at', { mode: 'timestamp' }),
	refreshTokenExpiresAt: integer('refresh_token_expires_at', { mode: 'timestamp' }),
	scope: text('scope'),
	password: text('password'),
	createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
	updatedAt: integer('updated_at', { mode: 'timestamp' }).notNull()
});

export const verification = sqliteTable('verification', {
	id: text('id').primaryKey(),
	identifier: text('identifier').notNull(),
	value: text('value').notNull(),
	expiresAt: integer('expires_at', { mode: 'timestamp' }).notNull(),
	createdAt: integer('created_at', { mode: 'timestamp' }),
	updatedAt: integer('updated_at', { mode: 'timestamp' })
});

// ---------------------------------------------------------------------------
// Per-user preferences
// ---------------------------------------------------------------------------

export const userSettings = sqliteTable('user_settings', {
	userId: text('user_id')
		.primaryKey()
		.references(() => user.id, { onDelete: 'cascade' }),
	// "HH:MM" 24-hour, interpreted in `timezone`
	editionTime: text('edition_time').notNull().default('07:00'),
	// IANA timezone, e.g. "Africa/Harare"
	timezone: text('timezone').notNull().default('UTC'),
	theme: text('theme', { enum: ['system', 'light', 'dark'] })
		.notNull()
		.default('system'),
	// Hides the "Fetch now" button and any manual-refresh affordances.
	habitsMode: integer('habits_mode', { mode: 'boolean' }).notNull().default(false),
	// Default per-feed article cap, overridable per feed.
	defaultArticleCap: integer('default_article_cap').notNull().default(15),
	// ISO date (YYYY-MM-DD) of the most recently compiled edition.
	lastEditionDate: text('last_edition_date'),
	// JSON array of category names the user has collapsed.
	collapsedCategories: text('collapsed_categories').notNull().default('[]')
});

// ---------------------------------------------------------------------------
// Feeds & articles
// ---------------------------------------------------------------------------

export const feeds = sqliteTable('feeds', {
	id: text('id').primaryKey(),
	userId: text('user_id')
		.notNull()
		.references(() => user.id, { onDelete: 'cascade' }),
	url: text('url').notNull(),
	title: text('title').notNull(),
	category: text('category').notNull().default('General'),
	// Per-feed override for how many articles can enter a single edition.
	// NULL = fall back to userSettings.defaultArticleCap.
	articleCap: integer('article_cap'),
	// Display order within a category.
	position: integer('position').notNull().default(0),
	lastFetchedAt: integer('last_fetched_at', { mode: 'timestamp' }),
	lastFetchError: text('last_fetch_error'),
	etag: text('etag'),
	lastModified: text('last_modified'),
	createdAt: integer('created_at', { mode: 'timestamp' }).notNull()
});

export const articles = sqliteTable(
	'articles',
	{
		id: text('id').primaryKey(),
		feedId: text('feed_id')
			.notNull()
			.references(() => feeds.id, { onDelete: 'cascade' }),
		// Stable identifier from the feed (guid/id, or a hash fallback).
		guid: text('guid').notNull(),
		title: text('title').notNull(),
		url: text('url').notNull(),
		author: text('author'),
		contentHtml: text('content_html'),
		excerpt: text('excerpt'),
		publishedAt: integer('published_at', { mode: 'timestamp' }),
		fetchedAt: integer('fetched_at', { mode: 'timestamp' }).notNull()
	},
	(table) => [unique('articles_feed_guid_unique').on(table.feedId, table.guid)]
);

// ---------------------------------------------------------------------------
// Editions: the frozen daily compilation
// ---------------------------------------------------------------------------

export const editions = sqliteTable(
	'editions',
	{
		id: text('id').primaryKey(),
		userId: text('user_id')
			.notNull()
			.references(() => user.id, { onDelete: 'cascade' }),
		date: text('date').notNull(), // YYYY-MM-DD, in the user's timezone
		issueNumber: integer('issue_number').notNull(),
		createdAt: integer('created_at', { mode: 'timestamp' }).notNull()
	},
	(table) => [unique('editions_user_date_unique').on(table.userId, table.date)]
);

export const editionArticles = sqliteTable(
	'edition_articles',
	{
		id: text('id').primaryKey(),
		editionId: text('edition_id')
			.notNull()
			.references(() => editions.id, { onDelete: 'cascade' }),
		articleId: text('article_id')
			.notNull()
			.references(() => articles.id, { onDelete: 'cascade' }),
		position: integer('position').notNull().default(0),
		read: integer('read', { mode: 'boolean' }).notNull().default(false),
		// 0-100, persisted scroll progress within the article.
		scrollPercent: integer('scroll_percent').notNull().default(0),
		// Raw pixel offset, for restoring exact position.
		scrollOffset: integer('scroll_offset').notNull().default(0),
		updatedAt: integer('updated_at', { mode: 'timestamp' })
	},
	(table) => [unique('edition_articles_unique').on(table.editionId, table.articleId)]
);

export type UserSettings = typeof userSettings.$inferSelect;
export type Feed = typeof feeds.$inferSelect;
export type Article = typeof articles.$inferSelect;
export type Edition = typeof editions.$inferSelect;
export type EditionArticle = typeof editionArticles.$inferSelect;
