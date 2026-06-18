// Called frequently (debounced) from the article reader as the person
// scrolls, plus once when an article crosses the "read" threshold or is
// manually toggled. Ownership is enforced by joining through to the
// edition's userId — editionArticleId alone isn't guessable in practice
// (it's a random UUID), but we don't rely on that for authorization.
import { json, error } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import { db } from '$lib/server/db';
import { editionArticles, editions } from '$lib/server/db/schema';
import type { RequestHandler } from './$types';

interface ProgressPayload {
	scrollPercent?: number;
	scrollOffset?: number;
	read?: boolean;
}

export const POST: RequestHandler = async ({ params, request, locals }) => {
	if (!locals.user) throw error(401, 'Unauthorized');

	const body = (await request.json()) as ProgressPayload;

	const [row] = await db
		.select({ editionArticleId: editionArticles.id, userId: editions.userId })
		.from(editionArticles)
		.innerJoin(editions, eq(editionArticles.editionId, editions.id))
		.where(eq(editionArticles.id, params.id))
		.limit(1);

	if (!row || row.userId !== locals.user.id) {
		throw error(404, 'Article not found');
	}

	const update: Partial<typeof editionArticles.$inferInsert> = { updatedAt: new Date() };
	if (typeof body.scrollPercent === 'number') {
		update.scrollPercent = Math.max(0, Math.min(100, Math.round(body.scrollPercent)));
	}
	if (typeof body.scrollOffset === 'number') {
		update.scrollOffset = Math.max(0, Math.round(body.scrollOffset));
	}
	if (typeof body.read === 'boolean') {
		update.read = body.read;
	}

	await db.update(editionArticles).set(update).where(eq(editionArticles.id, params.id));

	return json({ ok: true });
};
