import { redirect, fail } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import { db } from '$lib/server/db';
import { userSettings } from '$lib/server/db/schema';
import { getOrCreateUserSettings } from '$lib/server/db/user-settings';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	if (!locals.user) throw redirect(302, '/login');

	const settings = await getOrCreateUserSettings(locals.user.id);

	return {
		settings,
		availableTimezones:
			typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : []
	};
};

export const actions: Actions = {
	update: async ({ request, locals }) => {
		if (!locals.user) throw redirect(302, '/login');

		const data = await request.formData();
		const editionTime = data.get('editionTime') as string;
		const timezone = data.get('timezone') as string;
		const theme = data.get('theme') as 'system' | 'light' | 'dark';
		const habitsMode = data.get('habitsMode') === 'on';
		const defaultArticleCap = parseInt((data.get('defaultArticleCap') as string) || '15', 10);

		if (!/^\d{2}:\d{2}$/.test(editionTime)) {
			return fail(400, { message: 'Edition time must be in HH:MM format.' });
		}
		if (defaultArticleCap < 5 || defaultArticleCap > 50) {
			return fail(400, { message: 'Article cap must be between 5 and 50.' });
		}

		await db
			.update(userSettings)
			.set({ editionTime, timezone, theme, habitsMode, defaultArticleCap })
			.where(eq(userSettings.userId, locals.user.id));

		return { success: true };
	}
};
