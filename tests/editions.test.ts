import { afterAll, beforeEach, expect, test } from 'bun:test';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { migrate } from 'drizzle-orm/bun-sqlite/migrator';
import { eq } from 'drizzle-orm';
import type { RequestEvent } from '@sveltejs/kit';

// Use a dedicated database and stub HTTP so tests never touch a real account or feed.
const directory = mkdtempSync(join(tmpdir(), 'quiet-feed-test-'));
const previousDatabasePath = process.env.DATABASE_PATH;
process.env.DATABASE_PATH = join(directory, 'test.db');
const { db, sqlite } = await import('../src/lib/server/db');
const { user, userSettings, feeds, articles, editions, editionArticles } = await import('../src/lib/server/db/schema');
const { compileEdition } = await import('../src/lib/server/edition/compiler');
const { getEditionView } = await import('../src/lib/server/edition/view');
const { actions } = await import('../src/routes/+page.server');
const { actions: settingsActions } = await import('../src/routes/settings/+page.server');
const { load: articleLoad } = await import('../src/routes/article/[id]/+page.server');
const originalFetch = globalThis.fetch;
globalThis.fetch = Object.assign(async () => new Response(null, { status: 304 }), { preconnect: originalFetch.preconnect });
migrate(db, { migrationsFolder: './drizzle' });

afterAll(() => {
	globalThis.fetch = originalFetch;
	if (previousDatabasePath === undefined) delete process.env.DATABASE_PATH;
	else process.env.DATABASE_PATH = previousDatabasePath;
	sqlite.close();
	rmSync(directory, { recursive: true, force: true });
});

beforeEach(() => {
	db.delete(user).run();
	db.insert(user).values({ id: 'reader', name: 'Reader', email: 'reader@example.com', createdAt: new Date(), updatedAt: new Date() }).run();
	db.insert(userSettings).values({ userId: 'reader', timezone: 'UTC' }).run();
	for (const id of ['a', 'b', 'c']) {
		db.insert(feeds).values({ id, userId: 'reader', title: id, url: `https://example.com/${id}`, createdAt: new Date() }).run();
		for (let i = 0; i < 25; i++) {
			db.insert(articles).values({ id: `${id}-${i}`, feedId: id, guid: `${i}`, title: `${id}-${i}`, url: 'https://example.com/story', publishedAt: new Date(2026, 0, 25 - i), fetchedAt: new Date() }).run();
		}
	}
});

function event<Route extends '/' | '/settings' = '/'>(fields: Record<string, string>, userId = 'reader'): RequestEvent<Record<string, string>, Route> {
	return {
		locals: { user: { id: userId } },
		request: new Request('http://localhost/', { method: 'POST', body: new URLSearchParams(fields) })
	} as unknown as RequestEvent<Record<string, string>, Route>;
}

async function selection() {
	const result = await compileEdition('reader');
	const view = (await getEditionView(result.editionId))!;
	return { result, view, stories: view.categories.flatMap((category) => category.articles) };
}

test('default edition budget bounds the whole issue and shares space across sources', async () => {
	const { result, stories } = await selection();
	expect(result.articleCount).toBe(20);
	expect(['a', 'b', 'c'].map((id) => stories.filter((story) => story.feedId === id).length)).toEqual([7, 7, 6]);
	expect(stories.filter((story) => story.feedId === 'a').map((story) => story.title)).toEqual(Array.from({ length: 7 }, (_, i) => `a-${i}`));
});

test('per-feed caps still apply and spare slots go to other sources', async () => {
	db.update(feeds).set({ articleCap: 5 }).where(eq(feeds.id, 'a')).run();
	db.update(userSettings).set({ editionArticleCap: 100 }).run();
	const { result, stories } = await selection();
	expect(result.articleCount).toBe(35);
	expect(stories.filter((story) => story.feedId === 'a')).toHaveLength(5);
});

test('small editions rotate their starting source and never repeat previously included articles', async () => {
	db.update(userSettings).set({ editionArticleCap: 2 }).run();
	const first = await selection();
	expect(first.stories.map((story) => story.feedId)).toEqual(['a', 'b']);
	db.update(editions).set({ date: '2000-01-01' }).where(eq(editions.id, first.result.editionId)).run();
	const next = await selection();
	expect(next.stories.map((story) => story.feedId)).toEqual(['b', 'c']);
	expect(next.stories.some((story) => first.stories.some((previous) => previous.articleId === story.articleId))).toBe(false);
});

test('changing the budget never changes an already frozen edition', async () => {
	const first = await selection();
	db.update(userSettings).set({ editionArticleCap: 1 }).run();
	const next = await selection();
	expect(next.result.editionId).toBe(first.result.editionId);
	expect(next.stories.map((story) => story.articleId)).toEqual(first.stories.map((story) => story.articleId));
});

test('closure persists without changing reading history or removing articles', async () => {
	const { result, stories } = await selection();
	db.update(editionArticles).set({ read: true, scrollPercent: 95, scrollOffset: 320 }).where(eq(editionArticles.id, stories[0].editionArticleId)).run();
	const before = db.select().from(editionArticles).all();
	await actions.closeEdition!(event({ editionId: result.editionId }));
	const view = (await getEditionView(result.editionId))!;
	expect(view.closedAt).toBeInstanceOf(Date);
	expect(view.totalCount).toBe(20);
	expect(view.readCount).toBe(1);
	expect(db.select().from(editionArticles).all()).toEqual(before);
	const loaded = await articleLoad({ ...event({}), params: { id: stories[0].editionArticleId } } as unknown as Parameters<typeof articleLoad>[0]);
	expect(loaded).toHaveProperty('backUrl', `/archive/${view.date}`);
});

test('another account cannot close the reader’s edition', async () => {
	const { result } = await selection();
	const response = await actions.closeEdition!(event({ editionId: result.editionId }, 'someone-else'));
	expect(response).toHaveProperty('status', 404);
	expect((await getEditionView(result.editionId))!.closedAt).toBeNull();
});

test('edition budget rejects missing, fractional, nonnumeric and out-of-range values', async () => {
	for (const value of ['', '0', '-1', '101', '1.5', 'NaN', 'Infinity']) {
		const response = await settingsActions.update!(event<'/settings'>({ editionTime: '07:00', timezone: 'UTC', theme: 'system', defaultArticleCap: '15', editionArticleCap: value }));
		expect(response).toHaveProperty('status', 400);
		expect(db.select().from(userSettings).get()!.editionArticleCap).toBe(20);
	}
	await settingsActions.update!(event<'/settings'>({ editionTime: '07:00', timezone: 'UTC', theme: 'system', defaultArticleCap: '15', editionArticleCap: '8' }));
	expect(db.select().from(userSettings).get()!.editionArticleCap).toBe(8);
});


test('simultaneous compilation produces one complete frozen issue', async () => {
	const [first, second] = await Promise.all([compileEdition('reader'), compileEdition('reader')]);
	expect(first.editionId).toBe(second.editionId);
	expect(db.select().from(editions).all()).toHaveLength(1);
	expect((await getEditionView(first.editionId))!.totalCount).toBe(20);
});

test('feeds with no eligible articles produce a quiet edition', async () => {
	db.delete(articles).run();
	const { result, view } = await selection();
	expect(result.articleCount).toBe(0);
	expect(view.totalCount).toBe(0);
	expect(view.closedAt).toBeNull();
});
