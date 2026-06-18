import { error } from '@sveltejs/kit';
import { eq, asc } from 'drizzle-orm';
import { db } from '$lib/server/db';
import { feeds } from '$lib/server/db/schema';
import { buildOpml, type ParsedOpmlFeed } from '$lib/server/feeds/opml';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ locals }) => {
	if (!locals.user) throw error(401, 'Unauthorized');

	const userFeeds = await db
		.select()
		.from(feeds)
		.where(eq(feeds.userId, locals.user.id))
		.orderBy(asc(feeds.category), asc(feeds.position));

	const byCategory = new Map<string, ParsedOpmlFeed[]>();
	for (const f of userFeeds) {
		const list = byCategory.get(f.category) ?? [];
		list.push({ title: f.title, url: f.url, category: f.category });
		byCategory.set(f.category, list);
	}

	const xml = buildOpml(byCategory);

	return new Response(xml, {
		headers: {
			'Content-Type': 'text/x-opml; charset=utf-8',
			'Content-Disposition': 'attachment; filename="quiet-feed-subscriptions.opml"'
		}
	});
};
