<script lang="ts">
	import { signUp } from '$lib/auth-client';
	import { goto } from '$app/navigation';

	let name = $state('');
	let email = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);

	async function handleSubmit(e: SubmitEvent) {
		e.preventDefault();
		error = '';

		if (password.length < 8) {
			error = 'Password must be at least 8 characters.';
			return;
		}

		loading = true;
		const result = await signUp.email({ name: name.trim() || email.split('@')[0], email, password });
		loading = false;

		if (result.error) {
			error = result.error.message ?? 'Could not create an account.';
			return;
		}
		goto('/');
	}
</script>

<svelte:head>
	<title>Create your account — Quiet Feed</title>
</svelte:head>

<div class="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6 py-16">
	<p class="font-mono-tight mb-1 text-xs uppercase" style="color: var(--color-ink-faint); letter-spacing: 0.1em;">
		Quiet Feed
	</p>
	<h1 class="font-display mb-2 text-3xl" style="color: var(--color-ink);">Start your subscription</h1>
	<p class="mb-8 text-sm" style="color: var(--color-ink-soft);">
		One account, one daily edition. No app stores involved.
	</p>

	<form onsubmit={handleSubmit} class="flex flex-col gap-4">
		<label class="flex flex-col gap-1.5">
			<span class="text-dateline">Name</span>
			<input
				type="text"
				bind:value={name}
				autocomplete="name"
				placeholder="Optional"
				class="rounded-sm border px-3 py-2 text-base outline-none"
				style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
			/>
		</label>

		<label class="flex flex-col gap-1.5">
			<span class="text-dateline">Email</span>
			<input
				type="email"
				bind:value={email}
				required
				autocomplete="email"
				class="rounded-sm border px-3 py-2 text-base outline-none"
				style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
			/>
		</label>

		<label class="flex flex-col gap-1.5">
			<span class="text-dateline">Password</span>
			<input
				type="password"
				bind:value={password}
				required
				minlength="8"
				autocomplete="new-password"
				class="rounded-sm border px-3 py-2 text-base outline-none"
				style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
			/>
			<span class="text-xs" style="color: var(--color-ink-faint);">At least 8 characters.</span>
		</label>

		{#if error}
			<p class="text-sm" style="color: var(--color-stamp);">{error}</p>
		{/if}

		<button
			type="submit"
			disabled={loading}
			class="font-mono-tight mt-2 rounded-sm px-4 py-2.5 text-sm uppercase tracking-wide disabled:opacity-50"
			style="background-color: var(--color-ink); color: var(--color-paper);"
		>
			{loading ? 'Creating account…' : 'Create account'}
		</button>
	</form>

	<p class="mt-6 text-sm" style="color: var(--color-ink-soft);">
		Already subscribed? <a href="/login" style="color: var(--color-airmail); text-decoration: underline;">Sign in</a>
	</p>
</div>
