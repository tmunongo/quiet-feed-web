<script lang="ts">
	import { enhance } from '$app/forms';

	let { data, form } = $props();
	const s = $derived(data.settings);

	// Common timezones first, since scrolling a full IANA list to find
	// "Africa/Harare" or "America/New_York" is exactly the kind of friction
	// this app is supposed to avoid.
	const commonTimezones = [
		'Africa/Harare',
		'Africa/Johannesburg',
		'Africa/Lagos',
		'Africa/Cairo',
		'Europe/London',
		'Europe/Berlin',
		'America/New_York',
		'America/Chicago',
		'America/Los_Angeles',
		'Asia/Dubai',
		'Asia/Kolkata',
		'Asia/Singapore',
		'Asia/Tokyo',
		'Australia/Sydney',
		'UTC'
	];

	const otherTimezones = $derived(data.availableTimezones.filter((tz) => !commonTimezones.includes(tz)));
</script>

<svelte:head>
	<title>Settings — Quiet Feed</title>
</svelte:head>

<div class="mx-auto max-w-xl px-5 py-10">
	<header class="mb-8">
		<p class="text-dateline mb-1">Preferences</p>
		<h1 class="font-display text-2xl" style="color: var(--color-ink);">Settings</h1>
	</header>

	{#if form?.message}
		<p class="mb-4 text-sm" style="color: var(--color-stamp);">{form.message}</p>
	{/if}
	{#if form?.success}
		<p class="mb-4 text-sm" style="color: var(--color-airmail);">Saved.</p>
	{/if}

	<form method="POST" action="?/update" use:enhance class="flex flex-col gap-6">
		<label class="flex flex-col gap-1.5">
			<span class="text-dateline">Edition delivery time</span>
			<input
				type="time"
				name="editionTime"
				value={s?.editionTime ?? '07:00'}
				required
				class="w-40 rounded-sm border px-3 py-2 text-sm"
				style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
			/>
			<span class="text-xs" style="color: var(--color-ink-faint);">
				Your feeds are fetched and frozen into one edition at this time, daily.
			</span>
		</label>

		<label class="flex flex-col gap-1.5">
			<span class="text-dateline">Timezone</span>
			<select
				name="timezone"
				class="w-full rounded-sm border px-3 py-2 text-sm"
				style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
			>
				<optgroup label="Common">
					{#each commonTimezones as tz}
						<option value={tz} selected={s?.timezone === tz}>{tz}</option>
					{/each}
				</optgroup>
				{#if otherTimezones.length > 0}
					<optgroup label="All timezones">
						{#each otherTimezones as tz}
							<option value={tz} selected={s?.timezone === tz}>{tz}</option>
						{/each}
					</optgroup>
				{/if}
			</select>
		</label>

		<label class="flex flex-col gap-1.5">
			<span class="text-dateline">Theme</span>
			<div class="flex gap-4 text-sm" style="color: var(--color-ink);">
				{#each [['system', 'System'], ['light', 'Light'], ['dark', 'Dark']] as [value, label]}
					<label class="flex items-center gap-1.5">
						<input type="radio" name="theme" {value} checked={s?.theme === value} />
						{label}
					</label>
				{/each}
			</div>
		</label>

		<label class="flex flex-col gap-1.5">
			<span class="text-dateline">Default article cap per feed</span>
			<input
				type="number"
				name="defaultArticleCap"
				min="5"
				max="50"
				value={s?.defaultArticleCap ?? 15}
				class="w-24 rounded-sm border px-3 py-2 text-sm"
				style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
			/>
			<span class="text-xs" style="color: var(--color-ink-faint);">
				How many stories a single feed can contribute to one edition, unless overridden per-feed.
			</span>
		</label>

		<label class="flex items-start gap-3">
			<input type="checkbox" name="habitsMode" checked={s?.habitsMode} class="mt-1" />
			<span>
				<span class="block text-sm" style="color: var(--color-ink);">Habits mode</span>
				<span class="block text-xs" style="color: var(--color-ink-faint);">
					Hides the "fetch now" button everywhere. You wait for the edition — that's the point.
				</span>
			</span>
		</label>

		<button
			type="submit"
			class="font-mono-tight mt-2 self-start rounded-sm px-5 py-2.5 text-sm uppercase tracking-wide"
			style="background-color: var(--color-ink); color: var(--color-paper);"
		>
			Save settings
		</button>
	</form>
</div>
