<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import { renderDispatchMarkdown } from '$lib/markdown';

	let { data, form } = $props();

	let progressPercent = $state(0);
	let isRegenerating = $state(false);
	let pollInterval: ReturnType<typeof setInterval> | null = null;

	function handleScroll() {
		const doc = document.documentElement;
		const scrollTop = doc.scrollTop || document.body.scrollTop;
		const scrollHeight = doc.scrollHeight - doc.clientHeight;
		const percent = scrollHeight > 0 ? Math.round((scrollTop / scrollHeight) * 100) : 100;
		progressPercent = Math.max(progressPercent, percent);
	}

	$effect(() => {
		if (data.summary?.status === 'generating') {
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

	onMount(() => {
		window.addEventListener('scroll', handleScroll, { passive: true });
	});

	onDestroy(() => {
		if (typeof window !== 'undefined') {
			window.removeEventListener('scroll', handleScroll);
		}
		if (pollInterval) {
			clearInterval(pollInterval);
			pollInterval = null;
		}
	});

	function dateLabel(dateStr: string): string {
		const d = new Date(dateStr + 'T00:00:00');
		return d.toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase();
	}

	const generateAction = $derived(
		`?/generateSummary${data.edition?.date ? `&date=${encodeURIComponent(data.edition.date)}` : ''}`
	);
</script>

<svelte:head>
	<title>The Morning Dispatch · Issue №{data.edition.issueNumber} — Quiet Feed</title>
</svelte:head>

<!-- Thin reading-progress line -->
<div class="fixed top-0 left-0 z-10 h-0.5 w-full" style="background-color: var(--color-line);">
	<div
		class="h-full transition-[width] duration-200"
		style="width: {progressPercent}%; background-color: var(--color-airmail);"
	></div>
</div>

<!-- Sticky floating "Back to edition" button -->
<a
	href={data.backUrl}
	class="fixed bottom-6 left-4 md:bottom-8 md:left-8 z-40 flex items-center justify-center h-11 w-11 md:h-auto md:w-auto md:px-4 md:py-2.5 rounded-full shadow-md hover:shadow-lg transition-all active:scale-95 group font-mono-tight text-xs font-medium"
	style="background-color: var(--color-stamp); color: var(--color-paper);"
	aria-label="Back to edition"
	title="Back to edition"
>
	<svg
		xmlns="http://www.w3.org/2000/svg"
		viewBox="0 0 20 20"
		fill="currentColor"
		class="w-5 h-5 md:w-4 md:h-4 md:mr-1.5 transition-transform group-hover:-translate-x-0.5"
	>
		<path
			fill-rule="evenodd"
			d="M17 10a.75.75 0 0 1-.75.75H5.612l4.158 3.96a.75.75 0 1 1-1.04 1.08l-5.5-5.25a.75.75 0 0 1 0-1.08l5.5-5.25a.75.75 0 0 1 0-1.08L5.612 9.25H16.25A.75.75 0 0 1 17 10z"
			clip-rule="evenodd"
		/>
	</svg>
	<span class="hidden md:inline">Back to edition</span>
</a>

<div class="mx-auto max-w-2xl px-5 py-12">
	<a href={data.backUrl} class="font-mono-tight mb-8 inline-block text-xs" style="color: var(--color-ink-faint);">
		← Back to edition
	</a>

	<header class="mb-10 border-b pb-6" style="border-color: var(--color-line);">
		<div class="flex items-start justify-between gap-4">
			<div>
				<p class="text-dateline mb-2">
					Issue №{data.edition.issueNumber} · {dateLabel(data.edition.date)}
				</p>
				<h1 class="font-display text-3xl md:text-4xl leading-tight" style="color: var(--color-ink);">
					The Morning Dispatch
				</h1>
				{#if data.summary && data.summary.status === 'completed'}
					<p class="font-mono-tight mt-2 text-xs" style="color: var(--color-ink-faint);">
						{(data.summary.promptTokens ?? 0) + (data.summary.completionTokens ?? 0)} tokens · {data.summary.model}
					</p>
				{/if}
			</div>

			{#if data.hasGeminiKey && data.aiDigestEnabled && data.summary}
				<form
					method="POST"
					action={generateAction}
					use:enhance={() => {
						isRegenerating = true;
						return async ({ update }) => {
							isRegenerating = false;
							await update();
						};
					}}
				>
					<button
						type="submit"
						disabled={isRegenerating}
						class="font-mono-tight rounded-sm border px-3 py-1.5 text-xs uppercase tracking-wider cursor-pointer hover:underline disabled:opacity-50"
						style="border-color: var(--color-line); color: var(--color-ink);"
					>
						{isRegenerating ? 'Composing...' : '↻ Regenerate'}
					</button>
				</form>
			{/if}
		</div>
	</header>

	{#if form?.summaryError}
		<div class="mb-6 rounded-sm border p-4 text-sm" style="border-color: var(--color-stamp); color: var(--color-stamp);">
			{form.summaryError}
		</div>
	{/if}

	{#if data.summary && data.summary.status === 'completed'}
		<article class="article-body font-body text-base md:text-lg leading-relaxed">
			{@html renderDispatchMarkdown(data.summary.contentMarkdown)}
		</article>

		<footer class="mt-16 border-t pt-8 text-center" style="border-color: var(--color-line);">
			<p class="font-display text-lg mb-2" style="color: var(--color-ink);">End of the Morning Dispatch.</p>
			<p class="text-xs mb-6" style="color: var(--color-ink-soft);">
				All articles referenced above remain in your edition index for full reading.
			</p>
			<a
				href={data.backUrl}
				class="font-mono-tight inline-block rounded-sm px-5 py-2.5 text-xs uppercase tracking-wider"
				style="background-color: var(--color-ink); color: var(--color-paper);"
			>
				Return to edition index
			</a>
		</footer>
	{:else if data.summary && data.summary.status === 'generating'}
		<div class="py-24 text-center">
			<p class="text-dateline mb-3">Composing dispatch</p>
			<h2 class="font-display text-xl mb-3 animate-pulse" style="color: var(--color-ink);">
				Synthesizing your edition with Gemini...
			</h2>
			<p class="text-xs" style="color: var(--color-ink-faint);">
				This takes just a few seconds. The page will update automatically when ready.
			</p>
		</div>
	{:else}
		<!-- No summary or failed -->
		<div class="py-20 text-center">
			<p class="text-dateline mb-3">No dispatch compiled</p>
			<h2 class="font-display text-2xl mb-3" style="color: var(--color-ink);">
				{data.summary?.status === 'failed' ? 'Synthesis Failed' : 'Ready to Synthesize'}
			</h2>
			<p class="mb-8 max-w-sm mx-auto text-sm" style="color: var(--color-ink-soft);">
				{#if data.summary?.status === 'failed'}
					{data.summary.errorMessage || 'An error occurred during synthesis.'}
				{:else}
					Generate an editorial morning summary of all stories compiled into this edition.
				{/if}
			</p>

			{#if data.hasGeminiKey && data.aiDigestEnabled}
				<form
					method="POST"
					action={generateAction}
					use:enhance={() => {
						isRegenerating = true;
						return async ({ update }) => {
							isRegenerating = false;
							await update();
						};
					}}
				>
					<button
						type="submit"
						disabled={isRegenerating}
						class="font-mono-tight rounded-sm px-5 py-2.5 text-sm uppercase tracking-wider cursor-pointer disabled:opacity-50"
						style="background-color: var(--color-ink); color: var(--color-paper);"
					>
						{isRegenerating ? 'Composing dispatch...' : '✨ Generate Dispatch Now'}
					</button>
				</form>
			{:else}
				<a
					href="/settings"
					class="font-mono-tight inline-block rounded-sm px-5 py-2.5 text-xs uppercase tracking-wider"
					style="background-color: var(--color-ink); color: var(--color-paper);"
				>
					Configure Gemini Key in Settings →
				</a>
			{/if}
		</div>
	{/if}
</div>

<style>
	.article-body :global(p) {
		margin-bottom: 1.25em;
	}
	.article-body :global(h1),
	.article-body :global(h2),
	.article-body :global(h3),
	.article-body :global(h4) {
		font-family: var(--font-display);
	}
	.article-body :global(ul) {
		margin-bottom: 1.25em;
		padding-left: 1.25em;
		list-style-type: disc;
	}
	.article-body :global(ol) {
		margin-bottom: 1.25em;
		padding-left: 1.25em;
		list-style-type: decimal;
	}
	.article-body :global(li) {
		margin-bottom: 0.35em;
	}
	.article-body :global(blockquote) {
		border-left: 2px solid var(--color-line);
		padding-left: 1em;
		font-style: italic;
		color: var(--color-ink-soft);
		margin-bottom: 1.25em;
	}
	.article-body :global(a) {
		color: var(--color-airmail);
		text-decoration: underline;
		font-weight: 500;
	}
</style>
