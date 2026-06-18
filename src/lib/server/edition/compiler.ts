// The edition compiler is the core ritual of Quiet Feed: it fetches every
// subscribed feed once, caps how many articles any single feed can
// contribute, and freezes the result into one immutable "Edition" row.
// Once compiled, an edition never changes shape — re-reading it tomorrow
// shows exactly what it showed today.
import { randomUUID } from 'node:crypto';
import { eq, and, desc, sql } from 'drizzle-orm';
import { db } from '../db';
import { feeds, articles, editions, editionArticles, userSettings, type Feed } from '../db/schema';
import { fetchAllFeedsForUser } from '../feeds/fetcher';
import { getOrCreateUserSettings } from '../db/user-settings';

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

	return true;
}

function effectiveCap(feed: Feed, defaultCap: number): number {
	return feed.articleCap ?? defaultCap;
}

/**
 * Fetches all of a user's feeds, then freezes a new Edition: per feed, takes
 * up to its article cap of the newest not-yet-included articles, ordered
 * newest-first within each feed, grouped by category for display.
 */
export async function compileEdition(userId: string): Promise<{ editionId: string; articleCount: number }> {
	const settings = await getOrCreateUserSettings(userId);

	await fetchAllFeedsForUser(userId);

	const userFeeds = await db.select().from(feeds).where(eq(feeds.userId, userId));

	const today = dateKeyInTimezone(new Date(), settings.timezone);

	const [{ count: priorEditions }] = await db
		.select({ count: sql<number>`count(*)` })
		.from(editions)
		.where(eq(editions.userId, userId));

	const editionId = randomUUID();
	await db.insert(editions).values({
		id: editionId,
		userId,
		date: today,
		issueNumber: priorEditions + 1,
		createdAt: new Date()
	});

	let position = 0;
	let totalArticles = 0;

	for (const feed of userFeeds) {
		const cap = effectiveCap(feed, settings.defaultArticleCap);

		// Articles for this feed that have never appeared in any prior
		// edition, newest first, capped — this is what keeps a high-volume
		// feed from drowning out a low-volume one, and keeps editions from
		// re-showing yesterday's stories.
		const candidateArticles = await db
			.select({ id: articles.id })
			.from(articles)
			.leftJoin(editionArticles, eq(editionArticles.articleId, articles.id))
			.where(and(eq(articles.feedId, feed.id), sql`${editionArticles.id} IS NULL`))
			.orderBy(desc(articles.publishedAt))
			.limit(cap);

		for (const { id: articleId } of candidateArticles) {
			await db.insert(editionArticles).values({
				id: randomUUID(),
				editionId,
				articleId,
				position: position++
			});
			totalArticles++;
		}
	}

	await db.update(userSettings).set({ lastEditionDate: today }).where(eq(userSettings.userId, userId));

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
