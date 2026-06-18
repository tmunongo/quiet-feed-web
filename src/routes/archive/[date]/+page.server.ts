import { error, redirect } from '@sveltejs/kit';
import { eq, and } from 'drizzle-orm';
import { db } from '$lib/server/db';
import { editions } from '$lib/server/db/schema';
import { getEditionView } from '$lib/server/edition/view';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, locals }) => {
	if (!locals.user) throw redirect(302, '/login');

	const [edition] = await db
		.select()
		.from(editions)
		.where(and(eq(editions.userId, locals.user.id), eq(editions.date, params.date)))
		.limit(1);

	if (!edition) throw error(404, 'No edition for that date.');

	const view = await getEditionView(edition.id);
	return { edition: view };
};
