<script lang="ts">
	import Seal from '$lib/components/Seal.svelte';

	let { data } = $props();

	function dateLabel(dateStr: string): string {
		const d = new Date(dateStr + 'T00:00:00');
		return d.toLocaleDateString('en-US', { day: '2-digit', month: 'short' }).toUpperCase();
	}
</script>

<svelte:head>
	<title>Issue №{data.edition?.issueNumber} — Quiet Feed Archive</title>
</svelte:head>

<div class="mx-auto max-w-2xl px-5 py-10">
	<a href="/archive" class="font-mono-tight mb-6 inline-block text-xs" style="color: var(--color-ink-faint);">
		← Back to archive
	</a>

	{#if data.edition}
		<header class="mb-8 flex items-start justify-between">
			<div>
				<p class="text-dateline mb-1">Issue №{data.edition.issueNumber} · {dateLabel(data.edition.date)}</p>
				<h1 class="font-display text-2xl" style="color: var(--color-ink);">Back issue</h1>
			</div>
			<Seal issueNumber={data.edition.issueNumber} dateLabel={dateLabel(data.edition.date)} size={56} />
		</header>

		<div class="flex flex-col gap-8">
			{#each data.edition.categories as cat}
				<section>
					<h2 class="font-display mb-3 border-b pb-2 text-lg" style="color: var(--color-ink); border-color: var(--color-line);">
						{cat.category}
					</h2>
					<ul class="flex flex-col">
						{#each cat.articles as article, i}
							<li class="rule py-3" class:border-0={i === 0}>
								<a href="/article/{article.editionArticleId}" style="opacity: {article.read ? '0.55' : '1'};">
									<h3 class="font-body text-lg leading-snug" style="color: var(--color-ink);">{article.title}</h3>
									<p class="text-dateline mt-1.5">{article.feedTitle}</p>
								</a>
							</li>
						{/each}
					</ul>
				</section>
			{/each}
		</div>
	{/if}
</div>
