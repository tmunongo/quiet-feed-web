import { redirect, fail } from '@sveltejs/kit';
import { db } from '$lib/server/db';
import { feeds, editions } from '$lib/server/db/schema';
import { eq, count, and } from 'drizzle-orm';
import { getOrCompileTodaysEdition, hasEditionForToday, compileEdition } from '$lib/server/edition/compiler';
import { getEditionView } from '$lib/server/edition/view';
import { getOrCreateUserSettings } from '$lib/server/db/user-settings';
import { generateAndSaveEditionSummary } from '$lib/server/edition/ai';
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

	const base = {
		editionTime: settings.editionTime,
		habitsMode: settings.habitsMode,
		collapsedCategories: JSON.parse(settings.collapsedCategories) as string[],
		feedCount,
		aiDigestEnabled: settings.aiDigestEnabled,
		hasGeminiKey: !!settings.geminiApiKey
	};

	// Brand-new account, no feeds yet — skip compilation and show the
	// onboarding empty state instead of a "Quiet day" edition with nothing in it.
	if (feedCount === 0) {
		return { ...base, edition: null };
	}

	const edition = await getOrCompileTodaysEdition(locals.user.id);

	if (!edition) {
		return { ...base, edition: null };
	}

	const view = await getEditionView(edition.id);

	return { ...base, edition: view };
};

export const actions: Actions = {
	closeEdition: async ({ request, locals }) => {
		if (!locals.user) throw redirect(302, '/login');

		const data = await request.formData();
		const editionId = data.get('editionId');
		if (typeof editionId !== 'string' || !editionId) {
			return fail(400, { message: 'Choose an edition to close.' });
		}

		const [closed] = await db.update(editions)
			.set({ closedAt: new Date() })
			.where(and(eq(editions.id, editionId), eq(editions.userId, locals.user.id)))
			.returning({ id: editions.id });
		if (!closed) return fail(404, { message: 'Edition not found.' });

		return { success: true };
	},
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
	},

	generateSummary: async ({ locals }) => {
		if (!locals.user) throw redirect(302, '/login');

		const edition = await getOrCompileTodaysEdition(locals.user.id);
		if (!edition) {
			return fail(404, { message: 'No edition available to summarize.' });
		}

		const res = await generateAndSaveEditionSummary(edition.id, locals.user.id, true);
		if (!res.success) {
			return fail(400, { summaryError: res.error || 'Failed to generate summary.' });
		}

		return { summarySuccess: true };
	}
};
