<script lang="ts">
	import { enhance } from '$app/forms';

	let { data, form } = $props();

	let showAddForm = $state(false);
	let editingId = $state<string | null>(null);
	let addSubmitting = $state(false);
	let starterSubmitting = $state(false);
	let importSubmitting = $state(false);

	const categories = $derived(
		Array.from(new Set((data.feeds ?? []).map((f) => f.category))).sort((a, b) => a.localeCompare(b))
	);

	function feedsInCategory(category: string) {
		return (data.feeds ?? []).filter((f) => f.category === category);
	}
</script>

<svelte:head>
	<title>Feeds — Quiet Feed</title>
</svelte:head>

<div class="mx-auto max-w-2xl px-5 py-10">
	<header class="mb-8 flex items-end justify-between">
		<div>
			<p class="text-dateline mb-1">Subscriptions</p>
			<h1 class="font-display text-2xl" style="color: var(--color-ink);">Your feeds</h1>
		</div>
		<div class="flex gap-3">
			<a href="/feeds/export" class="font-mono-tight text-xs uppercase" style="color: var(--color-ink-faint);">
				Export OPML
			</a>
		</div>
	</header>

	{#if form?.message}
		<p class="mb-4 text-sm" style="color: var(--color-stamp);">{form.message}</p>
	{/if}

	{#if !data.feeds?.length}
		<div class="mb-10 rounded-sm border p-6 text-center" style="border-color: var(--color-line);">
			<p class="mb-4 text-sm" style="color: var(--color-ink-soft);">
				No feeds yet. Start with a handful of recommended feeds, or bring your library over from
				another reader.
			</p>
			<form method="POST" action="?/addStarter" use:enhance={() => {
				starterSubmitting = true;
				return async ({ update }) => {
					await update();
					starterSubmitting = false;
				};
			}}>
				<button
					type="submit"
					disabled={starterSubmitting}
					class="font-mono-tight rounded-sm px-4 py-2 text-sm uppercase tracking-wide disabled:opacity-50"
					style="background-color: var(--color-ink); color: var(--color-paper);"
				>
					{starterSubmitting ? 'Adding…' : 'Add starter feeds'}
				</button>
			</form>
		</div>
	{:else}
		<div class="mb-10 flex flex-col gap-6">
			{#each categories as category}
				<section>
					<h2 class="font-display mb-2 text-base" style="color: var(--color-ink);">{category}</h2>
					<ul class="flex flex-col">
						{#each feedsInCategory(category) as feed, i}
							<li class="rule flex items-start justify-between gap-4 py-3" class:border-0={i === 0}>
								{#if editingId === feed.id}
									<form
										method="POST"
										action="?/updateFeed"
										use:enhance={() => {
											return async ({ result, update }) => {
												if (result.type === 'success') {
													editingId = null;
												}
												await update();
											};
										}}
										class="flex w-full flex-col gap-2"
									>
										<input type="hidden" name="id" value={feed.id} />
										<input
											name="title"
											value={feed.title}
											class="rounded-sm border px-2 py-1 text-sm"
											style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
										/>
										<div class="flex gap-2">
											<input
												name="category"
												value={feed.category}
												placeholder="Category"
												class="w-1/2 rounded-sm border px-2 py-1 text-sm"
												style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
											/>
											<input
												name="articleCap"
												type="number"
												min="5"
												max="50"
												value={feed.articleCap ?? ''}
												placeholder={`Cap (default ${data.defaultArticleCap})`}
												class="w-1/2 rounded-sm border px-2 py-1 text-sm"
												style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
											/>
										</div>
										<div class="flex gap-3">
											<button type="submit" class="font-mono-tight text-xs uppercase" style="color: var(--color-airmail);">
												Save
											</button>
											<button
												type="button"
												onclick={() => (editingId = null)}
												class="font-mono-tight text-xs uppercase"
												style="color: var(--color-ink-faint);"
											>
												Cancel
											</button>
										</div>
									</form>
								{:else}
									<div class="min-w-0">
										<p class="truncate font-body text-base" style="color: var(--color-ink);">{feed.title}</p>
										<p class="text-dateline mt-1 truncate">
											{feed.url}{feed.articleCap ? ` · cap ${feed.articleCap}` : ''}
										</p>
										{#if feed.lastFetchError}
											<p class="mt-1 text-xs" style="color: var(--color-stamp);">
												Last fetch failed: {feed.lastFetchError}
											</p>
										{/if}
									</div>
									<div class="flex flex-shrink-0 gap-3">
										<button
											onclick={() => (editingId = feed.id)}
											class="font-mono-tight text-xs uppercase"
											style="color: var(--color-ink-faint);"
										>
											Edit
										</button>
										<form method="POST" action="?/deleteFeed" use:enhance={() => {
											return async ({ update }) => {
												await update();
											};
										}}>
											<input type="hidden" name="id" value={feed.id} />
											<button type="submit" class="font-mono-tight text-xs uppercase" style="color: var(--color-stamp);">
												Remove
											</button>
										</form>
									</div>
								{/if}
							</li>
						{/each}
					</ul>
				</section>
			{/each}
		</div>
	{/if}

	<div class="flex flex-col gap-6 border-t pt-8" style="border-color: var(--color-line);">
		<div>
			<button
				onclick={() => (showAddForm = !showAddForm)}
				class="font-mono-tight text-sm uppercase tracking-wide"
				style="color: var(--color-ink);"
			>
				{showAddForm ? '− Cancel' : '+ Add a feed'}
			</button>

			{#if showAddForm}
				<form
					method="POST"
					action="?/addFeed"
					use:enhance={() => {
						addSubmitting = true;
						return async ({ result, update }) => {
							if (result.type === 'success') {
								showAddForm = false;
							}
							await update();
							addSubmitting = false;
						};
					}}
					class="mt-4 flex flex-col gap-3"
				>
					<label class="flex flex-col gap-1.5">
						<span class="text-dateline">Feed URL</span>
						<input
							name="url"
							type="url"
							required
							placeholder="https://example.com/feed.xml"
							class="rounded-sm border px-3 py-2 text-sm"
							style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
						/>
					</label>
					<label class="flex flex-col gap-1.5">
						<span class="text-dateline">Category</span>
						<input
							name="category"
							placeholder="Technology"
							class="rounded-sm border px-3 py-2 text-sm"
							style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
						/>
					</label>
					<div class="flex items-center gap-3">
						<button
							type="submit"
							disabled={addSubmitting}
							class="font-mono-tight self-start rounded-sm px-4 py-2 text-sm uppercase tracking-wide disabled:opacity-50"
							style="background-color: var(--color-ink); color: var(--color-paper);"
						>
							{addSubmitting ? 'Adding…' : 'Add feed'}
						</button>
						{#if addSubmitting}
							<span class="text-dateline text-xs">Fetching feed info…</span>
						{/if}
					</div>
				</form>
			{/if}
		</div>

		<div>
			<p class="text-dateline mb-2">Import from another reader</p>
			<form method="POST" action="?/importOpml" enctype="multipart/form-data" use:enhance={() => {
				importSubmitting = true;
				return async ({ update }) => {
					await update();
					importSubmitting = false;
				};
			}} class="flex items-center gap-3">
				<input
					name="opml"
					type="file"
					accept=".opml,.xml,text/x-opml,text/xml"
					required
					class="text-sm"
					style="color: var(--color-ink-soft);"
				/>
				<button
					type="submit"
					disabled={importSubmitting}
					class="font-mono-tight rounded-sm border px-3 py-1.5 text-xs uppercase tracking-wide disabled:opacity-50"
					style="border-color: var(--color-line); color: var(--color-ink-soft);"
				>
					{importSubmitting ? 'Importing…' : 'Import OPML'}
				</button>
			</form>
		</div>
	</div>
</div>
