import { json, error } from '@sveltejs/kit';
import { db } from '$lib/server/db';
import { userSettings } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ request, locals }) => {
	if (!locals.user) throw error(401, 'Unauthorized');

	const { collapsed } = (await request.json()) as { collapsed: string[] };

	await db
		.update(userSettings)
		.set({ collapsedCategories: JSON.stringify(collapsed) })
		.where(eq(userSettings.userId, locals.user.id));

	return json({ ok: true });
};
