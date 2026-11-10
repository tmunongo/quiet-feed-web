import { redirect } from '@sveltejs/kit';
import { eq, desc } from 'drizzle-orm';
import { db } from '$lib/server/db';
import { editions } from '$lib/server/db/schema';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	if (!locals.user) throw redirect(302, '/login');

	const rows = await db
		.select({
			id: editions.id,
			date: editions.date,
			issueNumber: editions.issueNumber
		})
		.from(editions)
		.where(eq(editions.userId, locals.user.id))
		.orderBy(desc(editions.date));

	return { editions: rows };
};
