import { DEFAULT_MODEL, getModelFallbackChain } from '$lib/ai/models';

export class GeminiAuthError extends Error {
	constructor(message: string) {
		super(message);
		this.name = 'GeminiAuthError';
	}
}

/**
 * Gemini API client and content distillation helpers for Quiet Feed.
 * Designed to minimize token consumption and provide clear error messages.
 */

export interface GeminiDigestResponse {
	markdown: string;
	promptTokens: number;
	completionTokens: number;
	modelUsed: string;
}

export interface DigestArticleInput {
	editionArticleId: string;
	title: string;
	feedTitle: string;
	category: string;
	excerpt: string | null;
	contentHtml: string | null;
}

/**
 * Strips HTML tags and normalizes whitespace to produce lean plain text.
 */
export function cleanText(htmlOrText: string | null): string {
	if (!htmlOrText) return '';
	return htmlOrText
		.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
		.replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '')
		.replace(/<[^>]+>/g, ' ')
		.replace(/&nbsp;/g, ' ')
		.replace(/&amp;/g, '&')
		.replace(/&lt;/g, '<')
		.replace(/&gt;/g, '>')
		.replace(/&quot;/g, '"')
		.replace(/&#39;/g, "'")
		.replace(/\s+/g, ' ')
		.replace(/\s+([.,;:!?])/g, '$1')
		.trim();
}

/**
 * Distills an article into a compact summary entry (max ~1,000 characters).
 * Token-saving principle: we only pass the headline, feed name, category, and
 * opening lead paragraph, keeping each article to roughly 150-200 tokens.
 */
export function distillArticle(article: DigestArticleInput): string {
	let text = cleanText(article.excerpt);
	if (!text && article.contentHtml) {
		text = cleanText(article.contentHtml);
	}
	// Cap excerpt to 1,000 characters (~150-200 words)
	if (text.length > 1000) {
		text = text.slice(0, 1000) + '...';
	}

	return `[Article ID: ${article.editionArticleId}]
Title: ${article.title}
Source: ${article.feedTitle} (${article.category})
Lead: ${text || '(No excerpt available)'}`;
}

/**
 * Validates a user's Google Gemini API key by listing models.
 */
export async function validateGeminiKey(apiKey: string): Promise<{ valid: boolean; error?: string }> {
	const trimmedKey = apiKey?.trim();
	if (!trimmedKey) {
		return { valid: false, error: 'API key cannot be empty.' };
	}

	try {
		const res = await fetch('https://generativelanguage.googleapis.com/v1beta/models', {
			method: 'GET',
			headers: {
				'x-goog-api-key': trimmedKey,
				'User-Agent': 'QuietFeed/1.0'
			},
			signal: AbortSignal.timeout(10_000)
		});

		if (res.ok) {
			return { valid: true };
		}

		const data = (await res.json().catch(() => ({}))) as { error?: { message?: string } };
		const message = data?.error?.message || `Google API error (HTTP ${res.status})`;
		return { valid: false, error: message };
	} catch (err) {
		if (err instanceof Error && (err.name === 'TimeoutError' || err.name === 'AbortError')) {
			return { valid: false, error: 'Connection timed out while validating API key (10s limit).' };
		}
		return {
			valid: false,
			error: err instanceof Error ? err.message : 'Network error connecting to Gemini API'
		};
	}
}

/**
 * Synthesizes a daily edition into a cohesive markdown dispatch in a single API call,
 * with automatic model fallbacks if a chosen model is retired or unavailable.
 */
export async function generateGeminiDigest({
	apiKey,
	model = DEFAULT_MODEL,
	articles,
	dateLabel,
	issueNumber
}: {
	apiKey: string;
	model?: string;
	articles: DigestArticleInput[];
	dateLabel: string;
	issueNumber: number;
}): Promise<GeminiDigestResponse> {
	if (!articles.length) {
		return {
			markdown: '_None of your subscribed feeds had new stories in this edition._',
			promptTokens: 0,
			completionTokens: 0,
			modelUsed: model
		};
	}

	const distilledStories = articles.map(distillArticle).join('\n\n---\n\n');

	const prompt = `You are the executive editor for Quiet Feed, a calm, distraction-free daily news publication.
Your task is to write "The Morning Dispatch" summarizing today's edition (Issue №${issueNumber} · ${dateLabel}).

Tone & Style:
- Restrained, intelligent, clear, and objective (in the tradition of The Economist or an executive intelligence briefing).
- DO NOT use clickbait or AI fluff ("In today's fast-paced digital world", "Dive into", "Unpack").
- Synthesize related stories together rather than giving a disjointed list.
- Length: Keep the entire dispatch concise, cohesive, and complete (roughly 600 to 1,200 words total). Group stories thematically; do not attempt to write an exhaustive standalone summary for every single headline.

Linking Requirement:
- Whenever you mention a specific article, ALWAYS link to it using its Article ID in this format: [Article Headline](/article/{Article ID})
- Use the exact Article ID provided in the brackets: e.g. [Open Source Breakthrough](/article/ea_12345).

Structure:
1. ### The Lead
   A 2-3 sentence overarching synthesis capturing the most important theme or development across the stories today.
2. ### Key Themes & Developments
   Group stories into 3-5 major topics (e.g. Technology & Systems, Global Affairs, Culture & Notes). Under each theme, summarize the key developments with concise narrative paragraphs, referencing the articles with markdown links.
3. ### Noted in Brief
   A short bulleted list of 3-5 isolated or noteworthy items that don't fit into the main themes.

Here are the distilled articles for today's edition:

${distilledStories}`;

	const candidateModels = getModelFallbackChain(model);
	const trimmedKey = apiKey?.trim();
	let lastError: Error | null = null;

	for (let i = 0; i < candidateModels.length; i++) {
		const currentModel = candidateModels[i];
		const isLast = i === candidateModels.length - 1;

		try {
			const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(
				currentModel
			)}:generateContent`;

			const response = await fetch(endpoint, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'x-goog-api-key': trimmedKey,
					'User-Agent': 'QuietFeed/1.0'
				},
				signal: AbortSignal.timeout(60_000),
				body: JSON.stringify({
					contents: [
						{
							role: 'user',
							parts: [{ text: prompt }]
						}
					],
					generationConfig: {
						temperature: 0.3,
						maxOutputTokens: 8192,
						thinkingConfig: {
							thinkingBudget: 0
						}
					}
				})
			});

			if (!response.ok) {
				const errData = (await response.json().catch(() => ({}))) as {
					error?: { message?: string; status?: string };
				};
				const errMsg = errData.error?.message || `HTTP ${response.status}: ${response.statusText}`;

				// If it's an authentication error (401 / 403), stop fallback attempts immediately
				if (response.status === 401 || response.status === 403) {
					throw new GeminiAuthError(`Gemini API error (${response.status}): ${errMsg}`);
				}

				// If model is retired or unavailable, and we have fallbacks, try the next model
				if (!isLast) {
					console.warn(
						`[Gemini] Model ${currentModel} failed (${errMsg}). Trying fallback model ${candidateModels[i + 1]}...`
					);
					lastError = new Error(`Gemini API error (${currentModel}): ${errMsg}`);
					continue;
				}

				throw new Error(`Gemini API error: ${errMsg}`);
			}

			const data = (await response.json()) as {
				candidates?: Array<{
					content?: {
						parts?: Array<{ text?: string }>;
					};
				}>;
				usageMetadata?: {
					promptTokenCount?: number;
					candidatesTokenCount?: number;
				};
			};

			const candidateText =
				data.candidates?.[0]?.content?.parts?.map((p) => p.text || '').join('') || '';

			if (!candidateText) {
				if (!isLast) {
					console.warn(`[Gemini] Model ${currentModel} returned empty text. Trying fallback...`);
					continue;
				}
				throw new Error('Gemini API returned an empty response.');
			}

			return {
				markdown: candidateText.trim(),
				promptTokens: data.usageMetadata?.promptTokenCount ?? 0,
				completionTokens: data.usageMetadata?.candidatesTokenCount ?? 0,
				modelUsed: currentModel
			};
		} catch (err) {
			if (err instanceof GeminiAuthError) {
				throw err;
			}

			const isAbort =
				err instanceof Error && (err.name === 'TimeoutError' || err.name === 'AbortError');
			const msg = isAbort
				? `Gemini request timed out after 60 seconds (${currentModel})`
				: err instanceof Error
					? err.message
					: 'Unknown Gemini API error';

			lastError = new Error(msg);

			if (!isLast) {
				console.warn(`[Gemini] Error with ${currentModel}: ${msg}. Trying fallback...`);
				continue;
			}
			throw lastError;
		}
	}

	throw lastError || new Error('Failed to generate summary with any available Gemini model.');
}

