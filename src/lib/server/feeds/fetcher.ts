// Fetches a single RSS/Atom feed, parses it, and upserts new articles.
// Uses ETag / Last-Modified so well-behaved feeds return 304 and cost us
// (and them) nothing on days where nothing changed.
import Parser from 'rss-parser';
import { randomUUID } from 'node:crypto';
import { eq, and } from 'drizzle-orm';
import { db } from '../db';
import { feeds, articles, type Feed } from '../db/schema';
import { sanitizeArticleHtml } from '../sanitize';

const parser = new Parser({
	timeout: 15_000,
	headers: { 'User-Agent': 'QuietFeed/1.0 (+https://github.com/, daily-digest reader)' }
});

export interface FetchResult {
	feedId: string;
	status: 'updated' | 'not-modified' | 'error';
	newArticleCount: number;
	error?: string;
}

function stableGuid(item: { guid?: string; id?: string; link?: string; title?: string }): string {
	return item.guid || item.id || item.link || item.title || randomUUID();
}

export async function fetchFeed(feed: Feed): Promise<FetchResult> {
	try {
		const headers: Record<string, string> = {};
		if (feed.etag) headers['If-None-Match'] = feed.etag;
		if (feed.lastModified) headers['If-Modified-Since'] = feed.lastModified;

		const res = await fetch(feed.url, { headers, redirect: 'follow' });

		if (res.status === 304) {
			await db
				.update(feeds)
				.set({ lastFetchedAt: new Date(), lastFetchError: null })
				.where(eq(feeds.id, feed.id));
			return { feedId: feed.id, status: 'not-modified', newArticleCount: 0 };
		}

		if (!res.ok) {
			const message = `HTTP ${res.status}`;
			await db
				.update(feeds)
				.set({ lastFetchedAt: new Date(), lastFetchError: message })
				.where(eq(feeds.id, feed.id));
			return { feedId: feed.id, status: 'error', newArticleCount: 0, error: message };
		}

		const xml = await res.text();
		const parsed = await parser.parseString(xml);

		let newCount = 0;
		for (const item of parsed.items) {
			const guid = stableGuid(item);
			const existing = await db
				.select({ id: articles.id })
				.from(articles)
				.where(and(eq(articles.feedId, feed.id), eq(articles.guid, guid)))
				.limit(1);

			if (existing.length > 0) continue;

			await db.insert(articles).values({
				id: randomUUID(),
				feedId: feed.id,
				guid,
				title: item.title?.trim() || '(untitled)',
				url: item.link || '',
				author: item.creator || item.author || null,
				contentHtml: sanitizeArticleHtml(item['content:encoded'] || item.content || item.summary),
				excerpt: item.contentSnippet?.slice(0, 400) || null,
				publishedAt: item.isoDate ? new Date(item.isoDate) : item.pubDate ? new Date(item.pubDate) : null,
				fetchedAt: new Date()
			});
			newCount++;
		}

		await db
			.update(feeds)
			.set({
				lastFetchedAt: new Date(),
				lastFetchError: null,
				etag: res.headers.get('etag') ?? null,
				lastModified: res.headers.get('last-modified') ?? null,
				// Adopt the feed's own title only if we don't already have one
				// the user has customized — keep it simple for now and only
				// set it if our current title looks like a bare placeholder.
				title: feed.title || parsed.title || feed.url
			})
			.where(eq(feeds.id, feed.id));

		return { feedId: feed.id, status: 'updated', newArticleCount: newCount };
	} catch (err) {
		const message = err instanceof Error ? err.message : 'Unknown fetch error';
		await db
			.update(feeds)
			.set({ lastFetchedAt: new Date(), lastFetchError: message })
			.where(eq(feeds.id, feed.id));
		return { feedId: feed.id, status: 'error', newArticleCount: 0, error: message };
	}
}

export async function fetchAllFeedsForUser(userId: string): Promise<FetchResult[]> {
	const userFeeds = await db.select().from(feeds).where(eq(feeds.userId, userId));
	const results: FetchResult[] = [];
	// Sequential, deliberately: this runs once a day in the background, not
	// on a user-facing critical path, so there's no reason to hammer many
	// feed hosts concurrently from one process.
	for (const feed of userFeeds) {
		results.push(await fetchFeed(feed));
	}
	return results;
}
