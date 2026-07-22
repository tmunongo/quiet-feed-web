import { getOrCreateUserSettings } from '$lib/server/db/user-settings';
import { appInfo } from '$lib/server/app-info';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ locals }) => {
	if (!locals.user) {
		return { user: null, settings: null, appInfo };
	}

	const settings = await getOrCreateUserSettings(locals.user.id);

	return {
		user: locals.user,
		settings,
		appInfo
	};
};
