import { redirect, fail } from '@sveltejs/kit';
import { db } from '$lib/server/db';
import { feeds } from '$lib/server/db/schema';
import { eq, count } from 'drizzle-orm';
import { getOrCompileTodaysEdition, hasEditionForToday, compileEdition } from '$lib/server/edition/compiler';
import { getEditionView } from '$lib/server/edition/view';
import { getOrCreateUserSettings } from '$lib/server/db/user-settings';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	if (!locals.user) {
		throw redirect(302, '/login');
	}

	const settings = await getOrCreateUserSettings(locals.user.id);

	const [{ value: feedCount }] = await db
		.select({ value: count() })
		.from(feeds)
		.where(eq(feeds.userId, locals.user.id));

	// Brand-new account, no feeds yet — send them to set up subscriptions
	// rather than showing an edition that can never have anything in it.
	const edition = await getOrCompileTodaysEdition(locals.user.id);

	const base = {
		editionTime: settings.editionTime,
		habitsMode: settings.habitsMode,
		collapsedCategories: JSON.parse(settings.collapsedCategories) as string[],
		feedCount
	};

	if (!edition) {
		return { ...base, edition: null };
	}

	const view = await getEditionView(edition.id);

	return { ...base, edition: view };
};

export const actions: Actions = {
	fetchNow: async ({ locals }) => {
		if (!locals.user) throw redirect(302, '/login');

		const settings = await getOrCreateUserSettings(locals.user.id);

		// Editions are frozen once compiled — "fetch now" only does anything
		// the first time today, otherwise it would defeat the entire point
		// of a single daily edition.
		if (await hasEditionForToday(locals.user.id, settings.timezone)) {
			return fail(409, { message: "Today's edition is already sealed." });
		}

		await compileEdition(locals.user.id);
		return { success: true };
	}
};
