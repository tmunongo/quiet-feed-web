// External-cron-friendly equivalent of the in-process scheduler. Point a
// systemd timer / cron job / cloud scheduler at this with:
//   POST /api/cron/compile
//   Authorization: Bearer <CRON_SECRET>
// Useful if ENABLE_INTERNAL_SCHEDULER is off (e.g. several app instances
// behind a load balancer, where you only want one external trigger).
import { json, error } from '@sveltejs/kit';
import { db } from '$lib/server/db';
import { userSettings } from '$lib/server/db/schema';
import { isEditionDue, compileEdition } from '$lib/server/edition/compiler';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ request }) => {
	const expected = process.env.CRON_SECRET;
	const provided = request.headers.get('authorization')?.replace(/^Bearer\s+/i, '');

	if (!expected || provided !== expected) {
		throw error(401, 'Unauthorized');
	}

	const allSettings = await db.select({ userId: userSettings.userId }).from(userSettings);
	const compiled: string[] = [];
	const failed: { userId: string; message: string }[] = [];

	for (const { userId } of allSettings) {
		try {
			if (await isEditionDue(userId)) {
				await compileEdition(userId);
				compiled.push(userId);
			}
		} catch (err) {
			failed.push({ userId, message: err instanceof Error ? err.message : 'Unknown error' });
		}
	}

	return json({ checked: allSettings.length, compiled: compiled.length, failed });
};
