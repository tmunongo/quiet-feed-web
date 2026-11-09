import { redirect, fail, error } from '@sveltejs/kit';
import { eq, and } from 'drizzle-orm';
import { db } from '$lib/server/db';
import { editions } from '$lib/server/db/schema';
import { getOrCompileTodaysEdition } from '$lib/server/edition/compiler';
import { getEditionSummary, generateAndSaveEditionSummary } from '$lib/server/edition/ai';
import { getOrCreateUserSettings } from '$lib/server/db/user-settings';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, url }) => {
	if (!locals.user) {
		throw redirect(302, '/login');
	}

	const settings = await getOrCreateUserSettings(locals.user.id);
	const dateParam = url.searchParams.get('date');

	let editionRow = null;
	let backUrl = '/';

	if (dateParam) {
		const [found] = await db
			.select()
			.from(editions)
			.where(and(eq(editions.userId, locals.user.id), eq(editions.date, dateParam)))
			.limit(1);

		if (!found) {
			throw error(404, 'No edition found for that date.');
		}
		editionRow = found;
		backUrl = `/archive/${dateParam}`;
	} else {
		editionRow = await getOrCompileTodaysEdition(locals.user.id);
		backUrl = '/';
	}

	if (!editionRow) {
		throw error(404, 'No edition available.');
	}

	const summary = await getEditionSummary(editionRow.id);

	return {
		edition: {
			id: editionRow.id,
			date: editionRow.date,
			issueNumber: editionRow.issueNumber
		},
		summary,
		backUrl,
		hasGeminiKey: !!settings.geminiApiKey,
		aiDigestEnabled: settings.aiDigestEnabled
	};
};

export const actions: Actions = {
	generateSummary: async ({ locals, url }) => {
		if (!locals.user) throw redirect(302, '/login');

		const dateParam = url.searchParams.get('date');
		let editionRow = null;

		if (dateParam) {
			const [found] = await db
				.select()
				.from(editions)
				.where(and(eq(editions.userId, locals.user.id), eq(editions.date, dateParam)))
				.limit(1);
			editionRow = found;
		} else {
			editionRow = await getOrCompileTodaysEdition(locals.user.id);
		}

		if (!editionRow) {
			return fail(404, { message: 'Edition not found.' });
		}

		const res = await generateAndSaveEditionSummary(editionRow.id, locals.user.id, true);
		if (!res.success) {
			return fail(400, { summaryError: res.error || 'Failed to generate dispatch summary.' });
		}

		return { success: true };
	}
};

