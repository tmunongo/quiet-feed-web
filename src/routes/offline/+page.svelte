<svelte:head>
	<title>You're offline — Quiet Feed</title>
</svelte:head>

<div
	class="flex min-h-screen flex-col items-center justify-center px-6 text-center"
	style="background-color: var(--color-paper); color: var(--color-ink);"
>
	<p class="text-dateline mb-3">No connection</p>
	<h1 class="font-display mb-3 text-2xl">You're offline.</h1>
	<p class="max-w-sm text-sm" style="color: var(--color-ink-soft);">
		Quiet Feed needs a connection to load a page you haven't already opened — but any edition you've
		already read should still be cached. Try going back, or reconnect and reload.
	</p>
</div>
