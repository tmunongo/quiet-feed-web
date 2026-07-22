<script lang="ts">
	import '../app.css';
	import { page } from '$app/stores';
	import { signOut } from '$lib/auth-client';
	import { goto, invalidateAll } from '$app/navigation';

	let { data, children } = $props();
	let mobileMenuOpen = $state(false);

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

	$effect(() => {
		// Close mobile menu on page navigation
		$page.url.pathname;
		mobileMenuOpen = false;
	});

	async function handleSignOut() {
		await signOut();
		await invalidateAll();
		goto('/login');
	}
</script>

<div class="flex min-h-screen flex-col" style="background-color: var(--color-paper); color: var(--color-ink);">
	{#if data.user}
		<header class="border-b relative" style="border-color: var(--color-line);">
			<div class="mx-auto flex max-w-3xl items-center justify-between px-5 py-4">
				<a href="/" onclick={() => (mobileMenuOpen = false)} class="font-mono-tight text-sm font-medium lowercase tracking-wide">
					quiet feed
				</a>

				<!-- Desktop Navigation -->
				<nav class="hidden md:flex items-center gap-5 text-sm">
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

				<!-- Mobile Hamburger Toggle -->
				<button
					onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
					class="flex md:hidden items-center justify-center p-1.5 rounded focus:outline-none cursor-pointer"
					style="color: var(--color-ink);"
					aria-label="Toggle navigation menu"
					aria-expanded={mobileMenuOpen}
				>
					{#if mobileMenuOpen}
						<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
						</svg>
					{:else}
						<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
						</svg>
					{/if}
				</button>
			</div>

			<!-- Mobile Menu Dropdown -->
			{#if mobileMenuOpen}
				<nav
					class="flex md:hidden flex-col border-t px-5 py-3 gap-3 text-base"
					style="background-color: var(--color-paper); border-color: var(--color-line);"
				>
					{#each navLinks as link}
						<a
							href={link.href}
							onclick={() => (mobileMenuOpen = false)}
							class="font-mono-tight py-1.5 transition-opacity"
							style="color: {$page.url.pathname === link.href
								? 'var(--color-ink)'
								: 'var(--color-ink-soft)'}; opacity: {$page.url.pathname === link.href ? '1' : '0.75'};"
						>
							{link.label}
						</a>
					{/each}
					<button
						onclick={() => {
							mobileMenuOpen = false;
							handleSignOut();
						}}
						class="font-mono-tight text-left py-1.5 cursor-pointer"
						style="color: var(--color-ink-faint);"
					>
						Sign out
					</button>
				</nav>
			{/if}
		</header>
	{/if}

	<main class="flex-1">
		{@render children()}
	</main>
</div>
