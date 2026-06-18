import { redirect, fail } from '@sveltejs/kit';
import { randomUUID } from 'node:crypto';
import { eq, and, asc } from 'drizzle-orm';
import { db } from '$lib/server/db';
import { feeds } from '$lib/server/db/schema';
import { getOrCreateUserSettings } from '$lib/server/db/user-settings';
import { parseOpml, type ParsedOpmlFeed } from '$lib/server/feeds/opml';
import Parser from 'rss-parser';
import type { Actions, PageServerLoad } from './$types';

const titleParser = new Parser({ timeout: 15_000 });

export const load: PageServerLoad = async ({ locals }) => {
	if (!locals.user) throw redirect(302, '/login');

	const userFeeds = await db
		.select()
		.from(feeds)
		.where(eq(feeds.userId, locals.user.id))
		.orderBy(asc(feeds.category), asc(feeds.position));

	const settings = await getOrCreateUserSettings(locals.user.id);

	return { feeds: userFeeds, defaultArticleCap: settings.defaultArticleCap };
};

export const actions: Actions = {
	addFeed: async ({ request, locals }) => {
		if (!locals.user) throw redirect(302, '/login');

		const data = await request.formData();
		const url = (data.get('url') as string)?.trim();
		const category = ((data.get('category') as string) || 'General').trim();

		if (!url) return fail(400, { message: 'A feed URL is required.' });

		let title = url;
		try {
			const parsed = await titleParser.parseURL(url);
			title = parsed.title?.trim() || url;
		} catch {
			// Still add the feed even if we can't fetch it right now — the
			// regular fetch cycle will retry and surface the error there.
		}

		await db.insert(feeds).values({
			id: randomUUID(),
			userId: locals.user.id,
			url,
			title,
			category,
			createdAt: new Date()
		});

		return { success: true };
	},

	updateFeed: async ({ request, locals }) => {
		if (!locals.user) throw redirect(302, '/login');

		const data = await request.formData();
		const id = data.get('id') as string;
		const title = (data.get('title') as string)?.trim();
		const category = (data.get('category') as string)?.trim();
		const articleCapRaw = data.get('articleCap') as string;
		const articleCap = articleCapRaw ? parseInt(articleCapRaw, 10) : null;

		if (!id || !title || !category) return fail(400, { message: 'Missing fields.' });

		await db
			.update(feeds)
			.set({ title, category, articleCap: articleCap && articleCap > 0 ? articleCap : null })
			.where(and(eq(feeds.id, id), eq(feeds.userId, locals.user.id)));

		return { success: true };
	},

	deleteFeed: async ({ request, locals }) => {
		if (!locals.user) throw redirect(302, '/login');

		const data = await request.formData();
		const id = data.get('id') as string;
		if (!id) return fail(400, { message: 'Missing feed id.' });

		await db.delete(feeds).where(and(eq(feeds.id, id), eq(feeds.userId, locals.user.id)));
		return { success: true };
	},

	addStarter: async ({ locals }) => {
		if (!locals.user) throw redirect(302, '/login');

		const starters: { url: string; category: string }[] = [
			{ url: 'https://hnrss.org/frontpage', category: 'Technology' },
			{ url: 'https://feeds.arstechnica.com/arstechnica/index', category: 'Technology' },
			{ url: 'https://www.theguardian.com/world/rss', category: 'News' },
			{ url: 'https://www.nasa.gov/feed/', category: 'Science' }
		];

		for (const starter of starters) {
			let title = starter.url;
			try {
				const parsed = await titleParser.parseURL(starter.url);
				title = parsed.title?.trim() || starter.url;
			} catch {
				/* fetch cycle will retry */
			}
			await db.insert(feeds).values({
				id: randomUUID(),
				userId: locals.user.id,
				url: starter.url,
				title,
				category: starter.category,
				createdAt: new Date()
			});
		}

		return { success: true };
	},

	importOpml: async ({ request, locals }) => {
		if (!locals.user) throw redirect(302, '/login');

		const data = await request.formData();
		const file = data.get('opml') as File | null;
		if (!file || file.size === 0) return fail(400, { message: 'Choose an OPML file first.' });

		const xml = await file.text();
		let parsedFeeds: ParsedOpmlFeed[];
		try {
			parsedFeeds = parseOpml(xml);
		} catch {
			return fail(400, { message: "Couldn't read that file as OPML." });
		}

		if (parsedFeeds.length === 0) {
			return fail(400, { message: 'No feeds found in that file.' });
		}

		const existing = await db
			.select({ url: feeds.url })
			.from(feeds)
			.where(eq(feeds.userId, locals.user.id));
		const existingUrls = new Set(existing.map((f) => f.url));

		let imported = 0;
		for (const f of parsedFeeds) {
			if (existingUrls.has(f.url)) continue;
			await db.insert(feeds).values({
				id: randomUUID(),
				userId: locals.user.id,
				url: f.url,
				title: f.title,
				category: f.category,
				createdAt: new Date()
			});
			imported++;
		}

		return { success: true, message: `Imported ${imported} of ${parsedFeeds.length} feeds.` };
	}
};
