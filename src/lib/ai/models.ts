export interface ModelOption {
	id: string;
	label: string;
}

export const DEFAULT_MODEL = 'gemini-3.6-flash';

export const SUPPORTED_MODELS: ModelOption[] = [
	{ id: 'gemini-3.6-flash', label: 'Gemini 3.6 Flash (Default — fast, high quality)' },
	{ id: 'gemini-3.8-flash', label: 'Gemini 3.8 Flash (Latest frontier capabilities)' },
	{ id: 'gemini-3.5-flash-lite', label: 'Gemini 3.5 Flash Lite (Lightweight, lowest latency)' },
	{ id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' }
];

export const ALLOWED_MODELS: string[] = SUPPORTED_MODELS.map((m) => m.id);

/**
 * Ordered fallback candidates if a chosen model is retired, unavailable, or temporarily down.
 */
export const MODEL_FALLBACKS: Record<string, string[]> = {
	'gemini-3.6-flash': ['gemini-3.8-flash', 'gemini-3.5-flash-lite', 'gemini-2.5-flash'],
	'gemini-3.8-flash': ['gemini-3.6-flash', 'gemini-3.5-flash-lite', 'gemini-2.5-flash'],
	'gemini-3.5-flash-lite': ['gemini-3.6-flash', 'gemini-3.8-flash', 'gemini-2.5-flash'],
	'gemini-2.5-flash': ['gemini-3.6-flash', 'gemini-3.8-flash', 'gemini-3.5-flash-lite']
};

export function getModelFallbackChain(primaryModel: string): string[] {
	const chain = [primaryModel];
	const fallbacks = MODEL_FALLBACKS[primaryModel] || [
		DEFAULT_MODEL,
		'gemini-3.8-flash',
		'gemini-3.5-flash-lite'
	];
	for (const fb of fallbacks) {
		if (!chain.includes(fb)) {
			chain.push(fb);
		}
	}
	return chain;
}

