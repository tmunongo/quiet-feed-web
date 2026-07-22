<script lang="ts">
	let { data } = $props();

	function formatDate(dateStr: string): string {
		const d = new Date(dateStr + 'T00:00:00');
		return d.toLocaleDateString('en-US', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
	}
</script>

<svelte:head>
	<title>Archive — Quiet Feed</title>
</svelte:head>

<div class="mx-auto max-w-2xl px-5 py-10">
	<header class="mb-8">
		<p class="text-dateline mb-1">Back issues</p>
		<h1 class="font-display text-2xl" style="color: var(--color-ink);">Archive</h1>
	</header>

	{#if !data.editions?.length}
		<p class="text-sm" style="color: var(--color-ink-soft);">No editions have been sealed yet.</p>
	{:else}
		<ul class="flex flex-col">
			{#each data.editions ?? [] as edition, i}
				<li class="rule py-4" class:border-0={i === 0}>
					<a href="/archive/{edition.date}" class="flex items-center justify-between">
						<div>
							<p class="font-body text-lg" style="color: var(--color-ink);">Issue №{edition.issueNumber}</p>
							<p class="text-dateline mt-1">{formatDate(edition.date)}</p>
						</div>
						<p class="font-mono-tight text-sm" style="color: var(--color-ink-faint);">
							{edition.readCount ?? 0}/{edition.articleCount}
						</p>
					</a>
				</li>
			{/each}
		</ul>
	{/if}
</div>
