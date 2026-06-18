import { redirect } from '@sveltejs/kit';
import { eq, desc } from 'drizzle-orm';
import { db } from '$lib/server/db';
import { editions, editionArticles } from '$lib/server/db/schema';
import { sql } from 'drizzle-orm';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	if (!locals.user) throw redirect(302, '/login');

	const rows = await db
		.select({
			id: editions.id,
			date: editions.date,
			issueNumber: editions.issueNumber,
			articleCount: sql<number>`count(${editionArticles.id})`,
			readCount: sql<number>`sum(case when ${editionArticles.read} then 1 else 0 end)`
		})
		.from(editions)
		.leftJoin(editionArticles, eq(editionArticles.editionId, editions.id))
		.where(eq(editions.userId, locals.user.id))
		.groupBy(editions.id)
		.orderBy(desc(editions.date));

	return { editions: rows };
};
