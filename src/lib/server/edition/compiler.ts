// The edition compiler is the core ritual of Quiet Feed: it fetches every
// subscribed feed once, shares a whole-edition budget across per-feed caps,
// and freezes the result into one immutable "Edition" row.
// Once compiled, an edition never changes shape — re-reading it tomorrow
// shows exactly what it showed today.
import { randomUUID } from 'node:crypto';
import { eq, and, desc, sql } from 'drizzle-orm';
import { db } from '../db';
import { feeds, articles, editions, editionArticles, userSettings, type Feed } from '../db/schema';
import { fetchAllFeedsForUser } from '../feeds/fetcher';
import { getOrCreateUserSettings } from '../db/user-settings';
import { generateAndSaveEditionSummary } from './ai';

/** YYYY-MM-DD for "now" as seen in the given IANA timezone. */
export function dateKeyInTimezone(date: Date, timezone: string): string {
	return new Intl.DateTimeFormat('en-CA', {
		timeZone: timezone,
		year: 'numeric',
		month: '2-digit',
		day: '2-digit'
	}).format(date); // en-CA gives YYYY-MM-DD directly
}

/** "HH:MM" for "now" as seen in the given IANA timezone. */
export function timeKeyInTimezone(date: Date, timezone: string): string {
	return new Intl.DateTimeFormat('en-GB', {
		timeZone: timezone,
		hour: '2-digit',
		minute: '2-digit',
		hour12: false
	}).format(date);
}

export async function hasEditionForToday(userId: string, timezone: string): Promise<boolean> {
	const today = dateKeyInTimezone(new Date(), timezone);
	const existing = await db
		.select({ id: editions.id })
		.from(editions)
		.where(and(eq(editions.userId, userId), eq(editions.date, today)))
		.limit(1);
	return existing.length > 0;
}

/**
 * Whether `userId`'s configured edition time has passed for "today" in their
 * timezone, and today's edition doesn't exist yet. This is what lets a
 * frozen edition show up reliably even on platforms where background
 * scheduling (Periodic Background Sync, etc.) isn't available or hasn't
 * fired — checked on every page load as a fallback, and by the scheduler.
 */
export async function isEditionDue(userId: string): Promise<boolean> {
	const settings = await getOrCreateUserSettings(userId);

	const now = new Date();
	const nowTime = timeKeyInTimezone(now, settings.timezone);
	const today = dateKeyInTimezone(now, settings.timezone);

	if (nowTime < settings.editionTime) return false;
	if (settings.lastEditionDate === today) return false;
	if (await hasEditionForToday(userId, settings.timezone)) return false;

	return true;
}

function effectiveCap(feed: Feed, defaultCap: number): number {
	return feed.articleCap ?? defaultCap;
}

/**
 * Fetches all of a user's feeds, then freezes a new Edition: per feed, takes
 * up to its article cap of the newest not-yet-included articles, then shares
 * the whole-edition budget round-robin across sources. Display groups by category.
 */
export async function compileEdition(userId: string): Promise<{ editionId: string; articleCount: number }> {
	const settings = await getOrCreateUserSettings(userId);
	const today = dateKeyInTimezone(new Date(), settings.timezone);

	// Check if today's edition already exists before fetching feeds
	const [existingEarly] = await db
		.select({ id: editions.id })
		.from(editions)
		.where(and(eq(editions.userId, userId), eq(editions.date, today)))
		.limit(1);

	if (existingEarly) {
		return { editionId: existingEarly.id, articleCount: 0 };
	}

	await fetchAllFeedsForUser(userId);

	// Double-check after fetching feeds to guard against race conditions
	const [existingLate] = await db
		.select({ id: editions.id })
		.from(editions)
		.where(and(eq(editions.userId, userId), eq(editions.date, today)))
		.limit(1);

	if (existingLate) {
		return { editionId: existingLate.id, articleCount: 0 };
	}

	const userFeeds = await db.select().from(feeds).where(eq(feeds.userId, userId)).orderBy(feeds.id);

	const [{ count: priorEditions }] = await db
		.select({ count: sql<number>`count(*)` })
		.from(editions)
		.where(eq(editions.userId, userId));

	// Gather newest, never-shown candidates per source before freezing the edition.
	const candidates: { id: string }[][] = [];
	for (const feed of userFeeds) {
		const rows = await db
			.select({ id: articles.id })
			.from(articles)
			.leftJoin(editionArticles, eq(editionArticles.articleId, articles.id))
			.where(and(eq(articles.feedId, feed.id), sql`${editionArticles.id} IS NULL`))
			.orderBy(desc(articles.publishedAt), desc(articles.fetchedAt), articles.id)
			.limit(Math.min(effectiveCap(feed, settings.defaultArticleCap), settings.editionArticleCap));
		if (rows.length) candidates.push(rows);
	}

	// One story per source per round. Rotate the first eligible source so small
	// editions don't always favour the same feeds when there are more sources than slots.
	const selected: { id: string }[] = [];
	const start = candidates.length ? priorEditions % candidates.length : 0;
	for (let round = 0; selected.length < settings.editionArticleCap; round++) {
		let added = false;
		for (let offset = 0; offset < candidates.length && selected.length < settings.editionArticleCap; offset++) {
			const article = candidates[(start + offset) % candidates.length][round];
			if (article) {
				selected.push(article);
				added = true;
			}
		}
		if (!added) break;
	}

	const editionId = randomUUID();
	try {
		// Publish the edition and its contents together: readers never see a
		// partially assembled edition, even if another request compiles concurrently.
		db.transaction((tx) => {
			tx.insert(editions).values({
				id: editionId,
				userId,
				date: today,
				issueNumber: priorEditions + 1,
				createdAt: new Date()
			}).run();
			for (const [position, article] of selected.entries()) {
				tx.insert(editionArticles).values({
					id: randomUUID(), editionId, articleId: article.id, position
				}).run();
			}
			tx.update(userSettings).set({ lastEditionDate: today }).where(eq(userSettings.userId, userId)).run();
		});
	} catch (err) {
		const [existing] = await db.select({ id: editions.id }).from(editions)
			.where(and(eq(editions.userId, userId), eq(editions.date, today))).limit(1);
		if (existing) return { editionId: existing.id, articleCount: 0 };
		throw err;
	}
	const totalArticles = selected.length;

	if (settings.aiDigestEnabled && settings.aiDigestTrigger === 'auto' && settings.geminiApiKey) {
		generateAndSaveEditionSummary(editionId, userId).catch((err) => {
			console.error(`[compiler] AI digest generation failed for user ${userId}:`, err);
		});
	}

	return { editionId, articleCount: totalArticles };
}

/**
 * Returns today's edition if it's already compiled, compiling it on the
 * spot if the scheduled time has passed and it doesn't exist yet. This is
 * the reliable fallback path: it guarantees a fresh edition shows up the
 * moment the user opens the app after their edition time, regardless of
 * whether any background scheduling fired.
 */
export async function getOrCompileTodaysEdition(userId: string) {
	const due = await isEditionDue(userId);
	if (due) {
		await compileEdition(userId);
	}

	const settings = await getOrCreateUserSettings(userId);
	const today = dateKeyInTimezone(new Date(), settings.timezone);

	const [edition] = await db
		.select()
		.from(editions)
		.where(and(eq(editions.userId, userId), eq(editions.date, today)))
		.limit(1);

	return edition ?? null;
}
