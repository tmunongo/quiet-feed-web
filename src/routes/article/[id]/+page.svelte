<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	let { data } = $props();

	let progressPercent = $state(data.scrollPercent);
	let isRead = $state(data.read);

	// /article/[id] reuses the same component instance across navigations
	// between two articles (only the dynamic param changes), so local state
	// seeded from `data` at mount time would otherwise leak from one
	// article's reading position into the next one. Reset explicitly
	// whenever the underlying article changes.
	$effect(() => {
		progressPercent = data.scrollPercent;
		isRead = data.read;

		if (data.scrollOffset > 0) {
			requestAnimationFrame(() => {
				window.scrollTo({ top: data.scrollOffset, behavior: 'instant' as ScrollBehavior });
			});
		} else {
			window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior });
		}
	});

	const READ_THRESHOLD = 92;

	function saveProgress(payload: { scrollPercent?: number; scrollOffset?: number; read?: boolean }) {
		fetch(`/article/${data.editionArticleId}/progress`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload),
			keepalive: true
		}).catch(() => {
			// Best-effort — a missed progress tick just means the reader's
			// position is a little stale next time, not worth surfacing.
		});
	}

	let saveTimer: ReturnType<typeof setTimeout> | null = null;

	function handleScroll() {
		const doc = document.documentElement;
		const scrollTop = doc.scrollTop || document.body.scrollTop;
		const scrollHeight = doc.scrollHeight - doc.clientHeight;
		const percent = scrollHeight > 0 ? Math.round((scrollTop / scrollHeight) * 100) : 100;

		progressPercent = Math.max(progressPercent, percent);

		if (saveTimer) clearTimeout(saveTimer);
		saveTimer = setTimeout(() => {
			const shouldMarkRead = !isRead && progressPercent >= READ_THRESHOLD;
			if (shouldMarkRead) isRead = true;
			saveProgress({
				scrollPercent: progressPercent,
				scrollOffset: Math.round(scrollTop),
				...(shouldMarkRead ? { read: true } : {})
			});
		}, 600);
	}

	function toggleRead() {
		isRead = !isRead;
		saveProgress({ read: isRead });
	}

	onMount(() => {
		window.addEventListener('scroll', handleScroll, { passive: true });
	});

	onDestroy(() => {
		if (typeof window !== 'undefined') {
			window.removeEventListener('scroll', handleScroll);
		}
		if (saveTimer) clearTimeout(saveTimer);
	});

	function formatDate(date: Date | null): string {
		if (!date) return '';
		return new Date(date).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' });
	}
</script>

<svelte:head>
	<title>{data.title} — Quiet Feed</title>
</svelte:head>

<!-- Thin reading-progress line, not a badge or a counter — just an
     unobtrusive sense of "how far through" -->
<div class="fixed top-0 left-0 z-10 h-0.5 w-full" style="background-color: var(--color-line);">
	<div
		class="h-full transition-[width] duration-200"
		style="width: {progressPercent}%; background-color: var(--color-airmail);"
	></div>
</div>

<div class="mx-auto max-w-xl px-5 py-12">
	<a href="/" class="font-mono-tight mb-8 inline-block text-xs" style="color: var(--color-ink-faint);">
		← Back to edition
	</a>

	<header class="mb-8">
		<p class="text-dateline mb-2">
			{data.feedTitle}{data.publishedAt ? ` · ${formatDate(data.publishedAt)}` : ''}
		</p>
		<h1 class="font-display text-3xl leading-tight" style="color: var(--color-ink);">{data.title}</h1>
		{#if data.author}
			<p class="mt-2 text-sm" style="color: var(--color-ink-soft);">By {data.author}</p>
		{/if}
	</header>

	{#if data.contentHtml}
		<article
			class="article-body font-body text-lg leading-relaxed"
			style="color: var(--color-ink);"
		>
			{@html data.contentHtml}
		</article>
	{:else}
		<div>
			{#if data.excerpt}
				<p class="font-body text-lg leading-relaxed" style="color: var(--color-ink);">{data.excerpt}</p>
			{/if}
			<p class="mt-6 text-sm" style="color: var(--color-ink-soft);">
				This feed only publishes a summary. Read the full piece on the publisher's site:
			</p>
		</div>
	{/if}

	<div class="mt-10 flex items-center justify-between border-t pt-6" style="border-color: var(--color-line);">
		<a
			href={data.url}
			target="_blank"
			rel="noopener noreferrer"
			class="font-mono-tight text-sm uppercase tracking-wide"
			style="color: var(--color-airmail);"
		>
			Read original ↗
		</a>
		<button
			onclick={toggleRead}
			class="font-mono-tight text-sm uppercase tracking-wide"
			style="color: var(--color-ink-faint);"
		>
			{isRead ? '✓ Marked read' : 'Mark as read'}
		</button>
	</div>
</div>

<style>
	.article-body :global(p) {
		margin-bottom: 1.25em;
	}
	.article-body :global(img) {
		max-width: 100%;
		height: auto;
		border-radius: 2px;
		margin: 1.5em 0;
	}
	.article-body :global(h2),
	.article-body :global(h3) {
		font-family: var(--font-display);
		margin-top: 1.75em;
		margin-bottom: 0.5em;
	}
	.article-body :global(blockquote) {
		border-left: 2px solid var(--color-line);
		padding-left: 1em;
		font-style: italic;
		color: var(--color-ink-soft);
	}
	.article-body :global(a) {
		color: var(--color-airmail);
		text-decoration: underline;
	}
	.article-body :global(pre) {
		overflow-x: auto;
		background-color: var(--color-paper-raised);
		padding: 1em;
		border-radius: 4px;
		font-family: var(--font-mono);
		font-size: 0.875em;
	}
</style>
