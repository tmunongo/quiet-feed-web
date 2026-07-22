<script lang="ts">
	import Seal from '$lib/components/Seal.svelte';
	import { enhance } from '$app/forms';
	import { untrack } from 'svelte';

	let { data, form } = $props();

	let collapsed = $state<Set<string>>(untrack(() => new Set(data.collapsedCategories)));

	function toggleCategory(category: string) {
		if (collapsed.has(category)) {
			collapsed.delete(category);
		} else {
			collapsed.add(category);
		}
		collapsed = new Set(collapsed);

		fetch('/api/settings/collapsed-categories', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ collapsed: Array.from(collapsed) })
		});
	}

	function dateLabel(dateStr: string): string {
		const d = new Date(dateStr + 'T00:00:00');
		return d.toLocaleDateString('en-US', { day: '2-digit', month: 'short' }).toUpperCase();
	}

	function timeAgo(date: Date | null): string {
		if (!date) return '';
		const d = new Date(date);
		return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
	}

	let isSealed = $derived(
		!!data.edition && data.edition.totalCount > 0 && data.edition.readCount === data.edition.totalCount
	);
</script>

<svelte:head>
	<title>Today's edition — Quiet Feed</title>
</svelte:head>

<div class="mx-auto max-w-2xl px-5 py-10">
	{#if !data.edition}
		{#if data.feedCount === 0}
			<!-- Genuinely new account: nothing to compile yet. -->
			<div class="flex flex-col items-center py-24 text-center">
				<p class="text-dateline mb-3">No edition yet</p>
				<h1 class="font-display mb-3 text-2xl" style="color: var(--color-ink);">
					Your first edition arrives at {data.editionTime}.
				</h1>
				<p class="mb-8 max-w-sm text-sm" style="color: var(--color-ink-soft);">
					Add a few feeds and Quiet Feed will quietly compile them into your first edition once
					the clock strikes your scheduled time.
				</p>
				<a
					href="/feeds"
					class="font-mono-tight rounded-sm px-5 py-2.5 text-sm uppercase tracking-wide"
					style="background-color: var(--color-ink); color: var(--color-paper);"
				>
					Add your feeds
				</a>
			</div>
		{:else}
			<!-- Feeds exist, but the scheduled edition time hasn't passed today. -->
			<div class="flex flex-col items-center py-24 text-center">
				<p class="text-dateline mb-3">Next edition</p>
				<h1 class="font-display mb-3 text-2xl" style="color: var(--color-ink);">
					Arriving today at {data.editionTime}.
				</h1>
				<p class="mb-8 max-w-sm text-sm" style="color: var(--color-ink-soft);">
					{data.feedCount} feed{data.feedCount === 1 ? '' : 's'} subscribed. Quiet Feed checks them
					quietly in the background — there's nothing to do until your edition is ready.
				</p>
				{#if !data.habitsMode}
					<form method="POST" action="?/fetchNow" use:enhance>
						<button
							type="submit"
							class="font-mono-tight rounded-sm border px-5 py-2.5 text-sm uppercase tracking-wide"
							style="border-color: var(--color-line); color: var(--color-ink-soft);"
						>
							Fetch now instead
						</button>
					</form>
					{#if form?.message}
						<p class="mt-3 text-sm" style="color: var(--color-ink-faint);">{form.message}</p>
					{/if}
				{/if}
			</div>
		{/if}
	{:else}
		<header class="mb-8 flex items-start justify-between">
			<div>
				<p class="text-dateline mb-1">Issue №{data.edition?.issueNumber} · {dateLabel(data.edition?.date ?? '')}</p>
				<h1 class="font-display text-3xl" style="color: var(--color-ink);">Today's edition</h1>
				{#if data.edition && data.edition.totalCount > 0}
					<p class="mt-2 text-sm" style="color: var(--color-ink-faint);">
						{data.edition.readCount} of {data.edition.totalCount} read
					</p>
				{/if}
			</div>
			{#if isSealed && data.edition}
				<Seal issueNumber={data.edition.issueNumber} dateLabel={dateLabel(data.edition.date)} size={64} />
			{/if}
		</header>

		{#if isSealed && data.edition}
			<div class="flex flex-col items-center py-20 text-center">
				<Seal issueNumber={data.edition.issueNumber} dateLabel={dateLabel(data.edition.date)} size={150} />
				<h2 class="font-display mt-8 text-2xl" style="color: var(--color-ink);">
					Edition closed for today.
				</h2>
				<p class="mt-2 text-sm" style="color: var(--color-ink-soft);">
					Next edition arrives tomorrow at {data.editionTime}.
				</p>
			</div>
		{:else if data.edition && data.edition.totalCount === 0}
			<div class="flex flex-col items-center py-20 text-center">
				<p class="text-dateline mb-3">Quiet day</p>
				<p class="max-w-sm text-sm" style="color: var(--color-ink-soft);">
					None of your feeds published anything new before this edition was sealed. That's not a
					bug — some days are just quiet.
				</p>
			</div>
		{:else if data.edition}
			<div class="flex flex-col gap-8">
				{#each data.edition.categories as cat}
					{@const isCollapsed = collapsed.has(cat.category)}
					<section>
						<button
							onclick={() => toggleCategory(cat.category)}
							class="mb-3 flex w-full items-center justify-between border-b pb-2 text-left"
							style="border-color: var(--color-line);"
						>
							<h2 class="font-display text-lg" style="color: var(--color-ink);">{cat.category}</h2>
							<span class="font-mono-tight text-xs" style="color: var(--color-ink-faint);">
								{cat.articles.length} {isCollapsed ? '▾' : '▴'}
							</span>
						</button>

						{#if !isCollapsed}
							<ul class="flex flex-col">
								{#each cat.articles as article, i}
									<li class="rule py-3" class:border-0={i === 0}>
										<a
											href="/article/{article.editionArticleId}"
											class="block"
											style="opacity: {article.read ? '0.55' : '1'};"
										>
											<h3 class="font-body text-lg leading-snug" style="color: var(--color-ink);">
												{article.title}
											</h3>
											<p class="text-dateline mt-1.5">
												{article.feedTitle}{article.publishedAt ? ` · ${timeAgo(article.publishedAt)}` : ''}
												{#if article.scrollPercent > 0 && !article.read}
													· {article.scrollPercent}% read
												{/if}
											</p>
										</a>
									</li>
								{/each}
							</ul>
						{/if}
					</section>
				{/each}
			</div>
		{/if}
	{/if}
</div>
