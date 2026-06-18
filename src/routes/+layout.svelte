<script lang="ts">
	import '../app.css';
	import { page } from '$app/stores';
	import { signOut } from '$lib/auth-client';
	import { goto, invalidateAll } from '$app/navigation';

	let { data, children } = $props();

	const navLinks = [
		{ href: '/', label: 'Edition' },
		{ href: '/feeds', label: 'Feeds' },
		{ href: '/archive', label: 'Archive' },
		{ href: '/settings', label: 'Settings' }
	];

	function applyTheme(theme: 'system' | 'light' | 'dark' | undefined) {
		const root = document.documentElement;
		const wantsDark =
			theme === 'dark' || (theme !== 'light' && window.matchMedia('(prefers-color-scheme: dark)').matches);
		root.classList.toggle('dark', wantsDark);
	}

	$effect(() => {
		applyTheme(data.settings?.theme);
		if (data.settings?.theme === 'system' || !data.settings) {
			const mq = window.matchMedia('(prefers-color-scheme: dark)');
			const listener = () => applyTheme(data.settings?.theme);
			mq.addEventListener('change', listener);
			return () => mq.removeEventListener('change', listener);
		}
	});

	async function handleSignOut() {
		await signOut();
		await invalidateAll();
		goto('/login');
	}
</script>

<div class="flex min-h-screen flex-col" style="background-color: var(--color-paper); color: var(--color-ink);">
	{#if data.user}
		<header class="border-b" style="border-color: var(--color-line);">
			<div class="mx-auto flex max-w-3xl items-center justify-between px-5 py-4">
				<a href="/" class="font-mono-tight text-sm font-medium lowercase tracking-wide">
					quiet feed
				</a>
				<nav class="flex items-center gap-5 text-sm">
					{#each navLinks as link}
						<a
							href={link.href}
							class="font-mono-tight transition-opacity"
							style="color: {$page.url.pathname === link.href
								? 'var(--color-ink)'
								: 'var(--color-ink-soft)'}; opacity: {$page.url.pathname === link.href ? '1' : '0.75'};"
						>
							{link.label}
						</a>
					{/each}
					<button
						onclick={handleSignOut}
						class="font-mono-tight cursor-pointer"
						style="color: var(--color-ink-faint);"
					>
						Sign out
					</button>
				</nav>
			</div>
		</header>
	{/if}

	<main class="flex-1">
		{@render children()}
	</main>
</div>
