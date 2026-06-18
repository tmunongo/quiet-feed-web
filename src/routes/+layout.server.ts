import { getOrCreateUserSettings } from '$lib/server/db/user-settings';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ locals }) => {
	if (!locals.user) {
		return { user: null, settings: null };
	}

	const settings = await getOrCreateUserSettings(locals.user.id);

	return {
		user: locals.user,
		settings
	};
};
