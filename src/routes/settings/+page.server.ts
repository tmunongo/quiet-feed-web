import { redirect, fail } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import { db } from '$lib/server/db';
import { userSettings } from '$lib/server/db/schema';
import { getOrCreateUserSettings } from '$lib/server/db/user-settings';
import { encryptSecret, decryptSecret, maskApiKey } from '$lib/server/crypto';
import { validateGeminiKey } from '$lib/server/ai/gemini';
import { ALLOWED_MODELS, DEFAULT_MODEL, SUPPORTED_MODELS } from '$lib/ai/models';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	if (!locals.user) throw redirect(302, '/login');

	const settings = await getOrCreateUserSettings(locals.user.id);
	const hasGeminiKey = !!settings.geminiApiKey;
	let maskedGeminiKey: string | null = null;

	if (settings.geminiApiKey) {
		const decrypted = decryptSecret(settings.geminiApiKey);
		if (decrypted) {
			maskedGeminiKey = maskApiKey(decrypted);
		}
	}

	return {
		settings: {
			...settings,
			geminiApiKey: null // Never leak encrypted ciphertext to the client
		},
		hasGeminiKey,
		maskedGeminiKey,
		supportedModels: SUPPORTED_MODELS,
		availableTimezones:
			typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : []
	};
};

export const actions: Actions = {
	update: async ({ request, locals }) => {
		if (!locals.user) throw redirect(302, '/login');

		const currentSettings = await getOrCreateUserSettings(locals.user.id);
		const data = await request.formData();

		const editionTime = data.get('editionTime') as string;
		const timezone = data.get('timezone') as string;
		const theme = data.get('theme') as 'system' | 'light' | 'dark';
		const habitsMode = data.get('habitsMode') === 'on';
		const defaultArticleCap = parseInt((data.get('defaultArticleCap') as string) || '15', 10);
		const editionArticleCap = Number(data.get('editionArticleCap'));

		const aiDigestEnabled = data.get('aiDigestEnabled') === 'on';

		const rawTrigger = data.get('aiDigestTrigger') as string;
		const aiDigestTrigger: 'manual' | 'auto' =
			rawTrigger === 'manual' || rawTrigger === 'auto'
				? rawTrigger
				: currentSettings.aiDigestTrigger;

		const aiModelCandidate = data.get('aiModel') as string;
		const aiModel = ALLOWED_MODELS.includes(aiModelCandidate)
			? aiModelCandidate
			: ALLOWED_MODELS.includes(currentSettings.aiModel)
				? currentSettings.aiModel
				: DEFAULT_MODEL;

		const newApiKey = (data.get('geminiApiKey') as string)?.trim();
		const removeKey = data.get('removeGeminiKey') === 'true';

		if (!/^\d{2}:\d{2}$/.test(editionTime)) {
			return fail(400, { message: 'Edition time must be in HH:MM format.' });
		}
		if (!Number.isInteger(editionArticleCap) || editionArticleCap < 1 || editionArticleCap > 100) {
			return fail(400, { message: 'Edition size must be a whole number between 1 and 100.' });
		}
		if (defaultArticleCap < 5 || defaultArticleCap > 50) {
			return fail(400, { message: 'Article cap must be between 5 and 50.' });
		}

		let finalApiKeyCipher = currentSettings.geminiApiKey;

		if (removeKey) {
			finalApiKeyCipher = null;
		} else if (newApiKey && !newApiKey.includes('••••')) {
			// Validate with Gemini API before saving
			const check = await validateGeminiKey(newApiKey);
			if (!check.valid) {
				return fail(400, { message: `Gemini API key validation failed: ${check.error}` });
			}
			finalApiKeyCipher = encryptSecret(newApiKey);
		}

		if (aiDigestEnabled && !finalApiKeyCipher) {
			return fail(400, {
				message: 'A valid Google Gemini API key is required to enable AI daily digests.'
			});
		}

		await db
			.update(userSettings)
			.set({
				editionTime,
				timezone,
				theme,
				habitsMode,
				defaultArticleCap,
				editionArticleCap,
				geminiApiKey: finalApiKeyCipher,
				aiModel,
				aiDigestEnabled: finalApiKeyCipher ? aiDigestEnabled : false,
				aiDigestTrigger
			})
			.where(eq(userSettings.userId, locals.user.id));

		return { success: true };
	},

	testGeminiKey: async ({ request, locals }) => {
		if (!locals.user) throw redirect(302, '/login');

		const data = await request.formData();
		const keyInput = (data.get('geminiApiKey') as string)?.trim();

		let keyToTest = keyInput;
		if (!keyToTest || keyToTest.includes('••••')) {
			const current = await getOrCreateUserSettings(locals.user.id);
			if (current.geminiApiKey) {
				keyToTest = decryptSecret(current.geminiApiKey) ?? '';
			}
		}

		if (!keyToTest) {
			return fail(400, { testError: 'No API key provided to test.' });
		}

		const check = await validateGeminiKey(keyToTest);
		if (!check.valid) {
			return fail(400, { testError: check.error || 'Invalid API key.' });
		}

		return { testSuccess: true, message: 'Google Gemini API key verified successfully!' };
	}
};
