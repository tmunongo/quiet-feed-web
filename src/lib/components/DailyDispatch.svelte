<script lang="ts">
	import type { EditionSummary } from '$lib/server/db/schema';
	import { enhance } from '$app/forms';
	import { onDestroy } from 'svelte';
	import { invalidateAll } from '$app/navigation';

	let {
		summary,
		canGenerate = false,
		issueNumber,
		totalArticles = 0,
		hasGeminiKey = false,
		aiDigestEnabled = false,
		dateParam = null
	}: {
		summary: EditionSummary | null;
		canGenerate?: boolean;
		issueNumber: number;
		totalArticles?: number;
		hasGeminiKey?: boolean;
		aiDigestEnabled?: boolean;
		dateParam?: string | null;
	} = $props();

	let isGenerating = $state(false);
	let errorMsg = $state<string | null>(null);
	let pollInterval: ReturnType<typeof setInterval> | null = null;

	$effect(() => {
		if (summary?.status === 'generating') {
			if (!pollInterval) {
				pollInterval = setInterval(() => {
					invalidateAll();
				}, 2500);
			}
		} else {
			if (pollInterval) {
				clearInterval(pollInterval);
				pollInterval = null;
			}
		}
	});

	onDestroy(() => {
		if (pollInterval) {
			clearInterval(pollInterval);
			pollInterval = null;
		}
	});

	const dispatchUrl = $derived(
		dateParam ? `/dispatch?date=${encodeURIComponent(dateParam)}` : '/dispatch'
	);

	function extractLeadText(markdown: string): string {
		if (!markdown) return '';
		const leadMatch = markdown.match(/###\s*The Lead\s*\n+([\s\S]*?)(?=\n+###|\n+##|$)/i);
		const rawText = leadMatch ? leadMatch[1] : markdown;
		return rawText
			.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
			.replace(/[*_#]/g, '')
			.trim();
	}

	const leadPreview = $derived(summary ? extractLeadText(summary.contentMarkdown) : '');
</script>

{#if summary && summary.status === 'completed'}
	<section
		class="mb-8 rounded-sm border p-5 md:p-6"
		style="background-color: var(--color-paper-raised); border-color: var(--color-line);"
	>
		<div class="flex items-start justify-between gap-4">
			<div>
				<p class="text-dateline mb-1.5">Executive Summary</p>
				<h2 class="font-display text-xl md:text-2xl font-semibold" style="color: var(--color-ink);">
					The Morning Dispatch
				</h2>
			</div>
			<a
				href={dispatchUrl}
				class="font-mono-tight whitespace-nowrap rounded-sm px-4 py-2 text-xs uppercase tracking-wider font-medium"
				style="background-color: var(--color-ink); color: var(--color-paper);"
			>
				Read Full Dispatch →
			</a>
		</div>

		{#if leadPreview}
			<p
				class="font-body text-base leading-relaxed mt-4 line-clamp-3 md:line-clamp-4"
				style="color: var(--color-ink);"
			>
				{leadPreview}
			</p>
		{/if}

		<div
			class="mt-4 pt-3 border-t flex items-center justify-between text-xs"
			style="border-color: var(--color-line);"
		>
			<span class="font-mono-tight" style="color: var(--color-ink-faint);">
				{(summary.promptTokens ?? 0) + (summary.completionTokens ?? 0)} tokens · {summary.model}
			</span>
			<a
				href={dispatchUrl}
				class="font-mono-tight uppercase text-[11px] underline"
				style="color: var(--color-airmail);"
			>
				Open full view ↗
			</a>
		</div>
	</section>
{:else if summary && summary.status === 'generating'}
	<section
		class="mb-8 rounded-sm border p-5 text-center"
		style="background-color: var(--color-paper-raised); border-color: var(--color-line);"
	>
		<p class="text-dateline mb-2">Composing dispatch</p>
		<p class="font-body text-sm animate-pulse" style="color: var(--color-ink-soft);">
			Synthesizing today's edition with Gemini...
		</p>
	</section>
{:else if canGenerate && totalArticles > 0}
	{@const displayError = errorMsg || (summary?.status === 'failed' ? summary.errorMessage : null)}
	<section
		class="mb-8 flex flex-col items-start justify-between gap-4 rounded-sm border p-4 sm:flex-row sm:items-center"
		style="background-color: var(--color-paper-raised); border-color: var(--color-line);"
	>
		<div>
			<div class="flex items-center gap-2">
				<h2 class="font-display text-base font-medium" style="color: var(--color-ink);">
					The Morning Dispatch
				</h2>
				<span
					class="font-mono-tight rounded-sm px-1.5 py-0.5 text-[10px] uppercase tracking-wider"
					style="background-color: var(--color-line); color: var(--color-ink-faint);"
				>
					AI Digest
				</span>
			</div>
			<p class="mt-0.5 text-xs" style="color: var(--color-ink-soft);">
				Synthesize today's {totalArticles} {totalArticles === 1 ? 'story' : 'stories'} into a cohesive morning brief.
			</p>
			{#if displayError}
				<p class="mt-1.5 text-xs font-mono" style="color: var(--color-stamp);">
					{displayError}
				</p>
			{/if}
		</div>

		<form
			method="POST"
			action="?/generateSummary"
			use:enhance={() => {
				isGenerating = true;
				errorMsg = null;
				return async ({ result, update }) => {
					isGenerating = false;
					if (result.type === 'failure') {
						errorMsg = (result.data?.summaryError as string) || 'Generation failed.';
					}
					await update();
				};
			}}
		>
			<button
				type="submit"
				disabled={isGenerating}
				class="font-mono-tight whitespace-nowrap rounded-sm px-4 py-2 text-xs uppercase tracking-wider cursor-pointer disabled:opacity-50 transition-opacity"
				style="background-color: var(--color-ink); color: var(--color-paper);"
			>
				{isGenerating
					? 'Composing...'
					: summary?.status === 'failed'
						? '↻ Retry Dispatch'
						: '✨ Generate Dispatch'}
			</button>
		</form>
	</section>
{:else if !hasGeminiKey && totalArticles > 0 && !aiDigestEnabled}
	<!-- Unobtrusive discovery note for users without an API key -->
	<div class="mb-6 flex items-center justify-between border-b pb-2 text-xs" style="border-color: var(--color-line);">
		<span class="text-dateline" style="color: var(--color-ink-faint);">
			Want an AI summary of this edition?
		</span>
		<a
			href="/settings"
			class="font-mono-tight hover:underline uppercase text-[11px]"
			style="color: var(--color-airmail);"
		>
			Add Gemini Key →
		</a>
	</div>
{/if}
