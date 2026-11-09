import { randomUUID } from 'node:crypto';
import { eq, asc, and, or, lt, ne } from 'drizzle-orm';
import { db } from '../db';
import {
	editions,
	editionArticles,
	articles,
	feeds,
	editionSummaries,
	userSettings,
	type EditionSummary
} from '../db/schema';
import { decryptSecret } from '../crypto';
import { generateGeminiDigest, type DigestArticleInput } from '../ai/gemini';
import { DEFAULT_MODEL } from '$lib/ai/models';

export async function getEditionSummary(editionId: string): Promise<EditionSummary | null> {
	const [summary] = await db
		.select()
		.from(editionSummaries)
		.where(eq(editionSummaries.editionId, editionId))
		.limit(1);

	return summary ?? null;
}

const STALE_GENERATING_MS = 5 * 60 * 1000; // 5 minutes (exceeds total timeout across all fallback model attempts)

export async function generateAndSaveEditionSummary(
	editionId: string,
	userId: string,
	force = false
): Promise<{ success: boolean; error?: string; summary?: EditionSummary }> {
	const [settings] = await db
		.select()
		.from(userSettings)
		.where(eq(userSettings.userId, userId))
		.limit(1);

	if (!settings?.geminiApiKey) {
		return { success: false, error: 'No Gemini API key configured in Settings.' };
	}

	const apiKey = decryptSecret(settings.geminiApiKey);
	if (!apiKey) {
		return { success: false, error: 'Could not decrypt Gemini API key.' };
	}

	const [edition] = await db
		.select()
		.from(editions)
		.where(and(eq(editions.id, editionId), eq(editions.userId, userId)))
		.limit(1);
	if (!edition) {
		return { success: false, error: 'Edition not found.' };
	}

	// If already completed and not forced, return existing summary
	const existing = await getEditionSummary(editionId);
	if (existing && existing.status === 'completed' && !force) {
		return { success: true, summary: existing };
	}

	const now = new Date();
	const staleThreshold = new Date(now.getTime() - STALE_GENERATING_MS);

	if (existing && existing.status === 'generating') {
		if (existing.createdAt > staleThreshold) {
			// Actively generating in another request
			return { success: true, summary: existing };
		}
	}

	const model = settings.aiModel || DEFAULT_MODEL;
	let summaryId = existing?.id;

	// Atomically claim generation
	if (existing) {
		const updateResult = await db
			.update(editionSummaries)
			.set({
				status: 'generating',
				errorMessage: null,
				createdAt: now
			})
			.where(
				and(
					eq(editionSummaries.id, existing.id),
					or(ne(editionSummaries.status, 'generating'), lt(editionSummaries.createdAt, staleThreshold))
				)
			)
			.returning({ id: editionSummaries.id });

		if (updateResult.length === 0) {
			// Another concurrent request claimed it
			const latest = await getEditionSummary(editionId);
			return { success: true, summary: latest ?? existing };
		}
		summaryId = updateResult[0].id;
	} else {
		summaryId = randomUUID();
		try {
			await db.insert(editionSummaries).values({
				id: summaryId,
				editionId,
				contentMarkdown: '',
				model,
				status: 'generating',
				createdAt: now
			});
		} catch {
			// Unique constraint hit by concurrent request
			const latest = await getEditionSummary(editionId);
			return { success: true, summary: latest ?? undefined };
		}
	}

	try {
		// Fetch edition articles in order
		const rows = await db
			.select({
				editionArticleId: editionArticles.id,
				title: articles.title,
				excerpt: articles.excerpt,
				contentHtml: articles.contentHtml,
				feedTitle: feeds.title,
				category: feeds.category
			})
			.from(editionArticles)
			.innerJoin(articles, eq(editionArticles.articleId, articles.id))
			.innerJoin(feeds, eq(articles.feedId, feeds.id))
			.where(eq(editionArticles.editionId, editionId))
			.orderBy(asc(editionArticles.position));

		const articleInputs: DigestArticleInput[] = rows.map((r) => ({
			editionArticleId: r.editionArticleId,
			title: r.title,
			feedTitle: r.feedTitle,
			category: r.category,
			excerpt: r.excerpt,
			contentHtml: r.contentHtml
		}));

		const result = await generateGeminiDigest({
			apiKey,
			model,
			articles: articleInputs,
			dateLabel: edition.date,
			issueNumber: edition.issueNumber
		});

		await db
			.update(editionSummaries)
			.set({
				contentMarkdown: result.markdown,
				model: result.modelUsed,
				promptTokens: result.promptTokens,
				completionTokens: result.completionTokens,
				status: 'completed',
				errorMessage: null
			})
			.where(eq(editionSummaries.id, summaryId));

		const [saved] = await db
			.select()
			.from(editionSummaries)
			.where(eq(editionSummaries.id, summaryId))
			.limit(1);

		return { success: true, summary: saved };
	} catch (err) {
		const message = err instanceof Error ? err.message : 'Failed to generate summary';
		await db
			.update(editionSummaries)
			.set({
				status: 'failed',
				errorMessage: message
			})
			.where(eq(editionSummaries.id, summaryId));

		return { success: false, error: message };
	}
}

