<script lang="ts">
	import { enhance, deserialize } from "$app/forms";
	import { untrack } from "svelte";
	import TimePicker from "$lib/components/TimePicker.svelte";
	import { SUPPORTED_MODELS } from "$lib/ai/models";

	let { data, form } = $props();
	const s = $derived(data.settings);

	// Local states for inputs, initialized from server-loaded settings.
	let editionTime = $state(
		untrack(() => data.settings?.editionTime ?? "07:00"),
	);
	let timezone = $state(untrack(() => data.settings?.timezone ?? "UTC"));
	let theme = $state<"system" | "light" | "dark">(
		untrack(() => data.settings?.theme ?? "system"),
	);
	let defaultArticleCap = $state(
		untrack(() => data.settings?.defaultArticleCap ?? 15),
	);
	let habitsMode = $state(untrack(() => data.settings?.habitsMode ?? false));

	let aiDigestEnabled = $state(
		untrack(() => data.settings?.aiDigestEnabled ?? false),
	);
	let aiDigestTrigger = $state<"manual" | "auto">(
		untrack(() => data.settings?.aiDigestTrigger ?? "manual"),
	);
	let aiModel = $state(
		untrack(() => data.settings?.aiModel ?? "gemini-3.6-flash"),
	);
	let geminiApiKey = $state(untrack(() => data.maskedGeminiKey ?? ""));
	let hasStoredKey = $state(untrack(() => data.hasGeminiKey));
	let removeGeminiKey = $state(false);
	let testStatus = $state<{
		loading: boolean;
		success?: boolean;
		message?: string;
	}>({ loading: false });

	async function testApiKey() {
		testStatus = { loading: true };
		const formData = new FormData();
		formData.append("geminiApiKey", geminiApiKey);

		try {
			const res = await fetch("?/testGeminiKey", {
				method: "POST",
				headers: {
					"x-sveltekit-action": "true",
				},
				body: formData,
			});
			const result = deserialize(await res.text());
			if (result.type === "success") {
				testStatus = {
					loading: false,
					success: true,
					message: "Gemini API key is valid!",
				};
			} else if (result.type === "failure") {
				testStatus = {
					loading: false,
					success: false,
					message:
						(result.data?.testError as string) ||
						(result.data?.message as string) ||
						"Key validation failed.",
				};
			} else {
				testStatus = {
					loading: false,
					success: false,
					message: "Key validation failed.",
				};
			}
		} catch (e) {
			testStatus = {
				loading: false,
				success: false,
				message: "Could not test key due to a network error.",
			};
		}
	}

	// Common timezones first
	const commonTimezones = [
		"Africa/Harare",
		"Africa/Johannesburg",
		"Africa/Lagos",
		"Africa/Cairo",
		"Europe/London",
		"Europe/Berlin",
		"America/New_York",
		"America/Chicago",
		"America/Los_Angeles",
		"Asia/Dubai",
		"Asia/Kolkata",
		"Asia/Singapore",
		"Asia/Tokyo",
		"Australia/Sydney",
		"UTC",
	];

	const otherTimezones = $derived(
		(data.availableTimezones ?? []).filter(
			(tz) => !commonTimezones.includes(tz),
		),
	);
</script>

<svelte:head>
	<title>Settings — Quiet Feed</title>
</svelte:head>

<div class="mx-auto max-w-xl px-5 py-10">
	<header class="mb-8">
		<p class="text-dateline mb-1">Preferences</p>
		<h1 class="font-display text-2xl" style="color: var(--color-ink);">
			Settings
		</h1>
	</header>

	{#if form?.message}
		<p class="mb-4 text-sm" style="color: var(--color-stamp);">
			{form.message}
		</p>
	{/if}
	{#if form?.success}
		<p class="mb-4 text-sm" style="color: var(--color-airmail);">Saved.</p>
	{/if}

	<form
		method="POST"
		action="?/update"
		use:enhance={() => {
			return async ({ result, update }) => {
				await update({ reset: false });
				if (result.type === "success" && data.settings) {
					editionTime = data.settings.editionTime;
					timezone = data.settings.timezone;
					theme = data.settings.theme;
					defaultArticleCap = data.settings.defaultArticleCap;
					habitsMode = data.settings.habitsMode;
					aiDigestEnabled = data.settings.aiDigestEnabled;
					aiDigestTrigger = data.settings.aiDigestTrigger;
					aiModel = data.settings.aiModel;
					hasStoredKey = data.hasGeminiKey;
					geminiApiKey = data.maskedGeminiKey ?? "";
					removeGeminiKey = false;
				}
			};
		}}
		class="flex flex-col gap-6"
	>
		<div class="flex flex-col gap-1.5">
			<span class="text-dateline">Edition delivery time</span>
			<TimePicker name="editionTime" bind:value={editionTime} />
			<span class="text-xs" style="color: var(--color-ink-faint);">
				Your feeds are fetched and frozen into one edition at this time,
				daily.
			</span>
		</div>

		<label class="flex flex-col gap-1.5">
			<span class="text-dateline">Timezone</span>
			<select
				name="timezone"
				bind:value={timezone}
				class="w-full rounded-sm border px-3 py-2 text-sm"
				style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
			>
				<optgroup label="Common">
					{#each commonTimezones as tz}
						<option value={tz}>{tz}</option>
					{/each}
				</optgroup>
				{#if otherTimezones.length > 0}
					<optgroup label="All timezones">
						{#each otherTimezones as tz}
							<option value={tz}>{tz}</option>
						{/each}
					</optgroup>
				{/if}
			</select>
		</label>

		<label class="flex flex-col gap-1.5">
			<span class="text-dateline">Theme</span>
			<div class="flex gap-4 text-sm" style="color: var(--color-ink);">
				{#each [["system", "System"], ["light", "Light"], ["dark", "Dark"]] as [val, label]}
					<label class="flex items-center gap-1.5">
						<input
							type="radio"
							name="theme"
							value={val}
							bind:group={theme}
						/>
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
				bind:value={defaultArticleCap}
				class="w-24 rounded-sm border px-3 py-2 text-sm"
				style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
			/>
			<span class="text-xs" style="color: var(--color-ink-faint);">
				How many stories a single feed can contribute to one edition,
				unless overridden per-feed.
			</span>
		</label>

		<label class="flex items-start gap-3">
			<input
				type="checkbox"
				name="habitsMode"
				bind:checked={habitsMode}
				class="mt-1"
			/>
			<span>
				<span class="block text-sm" style="color: var(--color-ink);"
					>Habits mode</span
				>
				<span
					class="block text-xs"
					style="color: var(--color-ink-faint);"
				>
					Hides the "fetch now" button everywhere. Just wait for the
					edition.
				</span>
			</span>
		</label>

		<div
			class="my-2 border-t pt-6"
			style="border-color: var(--color-line);"
		>
			<h2 class="font-display text-lg" style="color: var(--color-ink);">
				AI Daily Digest (Google Gemini)
			</h2>
			<p class="mt-1 text-xs" style="color: var(--color-ink-soft);">
				Synthesize your daily edition into an editorial morning
				dispatch. We distill story excerpts and send a single batched
				prompt per edition to keep token consumption minimal.
			</p>
		</div>

		<label class="flex flex-col gap-1.5">
			<span class="text-dateline">Google Gemini API Key</span>
			<div class="flex gap-2">
				<input
					type="password"
					name="geminiApiKey"
					bind:value={geminiApiKey}
					placeholder="AIzaSy..."
					autocomplete="off"
					class="flex-1 rounded-sm border px-3 py-2 text-sm font-mono"
					style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
				/>
				<button
					type="button"
					onclick={testApiKey}
					disabled={testStatus.loading || !geminiApiKey}
					class="font-mono-tight rounded-sm border px-3 py-2 text-xs uppercase tracking-wider cursor-pointer disabled:opacity-50"
					style="border-color: var(--color-line); color: var(--color-ink);"
				>
					{testStatus.loading ? "Testing..." : "Test Key"}
				</button>
			</div>
			{#if testStatus.message}
				<p
					class="text-xs {testStatus.success
						? 'text-green-700 dark:text-green-400'
						: 'text-red-700 dark:text-red-400'}"
				>
					{testStatus.message}
				</p>
			{/if}
			{#if hasStoredKey}
				<div class="flex items-center gap-2 mt-1">
					<label
						class="flex items-center gap-1.5 text-xs cursor-pointer"
						style="color: var(--color-stamp);"
					>
						<input
							type="checkbox"
							name="removeGeminiKey"
							value="true"
							bind:checked={removeGeminiKey}
						/>
						Remove saved API key
					</label>
				</div>
			{/if}
			<span class="text-xs" style="color: var(--color-ink-faint);">
				Stored encrypted on your server. Get a free API key with a
				generous free tier from
				<a
					href="https://aistudio.google.com/"
					target="_blank"
					rel="noopener noreferrer"
					class="underline"
					style="color: var(--color-airmail);">Google AI Studio</a
				>.
			</span>
		</label>

		<label class="flex items-start gap-3">
			<input
				type="checkbox"
				name="aiDigestEnabled"
				bind:checked={aiDigestEnabled}
				class="mt-1"
			/>
			<span>
				<span class="block text-sm" style="color: var(--color-ink);"
					>Enable AI Daily Digest</span
				>
				<span
					class="block text-xs"
					style="color: var(--color-ink-faint);"
				>
					Create an editorial summary for each edition.
				</span>
			</span>
		</label>

		{#if aiDigestEnabled}
			<label class="flex flex-col gap-1.5">
				<span class="text-dateline">Digest Delivery Timing</span>
				<div
					class="flex flex-col gap-2 text-sm"
					style="color: var(--color-ink);"
				>
					<label class="flex items-start gap-2">
						<input
							type="radio"
							name="aiDigestTrigger"
							value="manual"
							bind:group={aiDigestTrigger}
							class="mt-1"
						/>
						<div>
							<span class="font-medium"
								>On-Demand (Recommended)</span
							>
							<p
								class="text-xs"
								style="color: var(--color-ink-faint);"
							>
								Generate only when you click "Generate Daily
								Dispatch" on today's edition. Spends zero tokens
								on days you don't open the app.
							</p>
						</div>
					</label>
					<label class="flex items-start gap-2">
						<input
							type="radio"
							name="aiDigestTrigger"
							value="auto"
							bind:group={aiDigestTrigger}
							class="mt-1"
						/>
						<div>
							<span class="font-medium">Automatic</span>
							<p
								class="text-xs"
								style="color: var(--color-ink-faint);"
							>
								Silently synthesize the dispatch in the
								background the moment your edition arrives.
							</p>
						</div>
					</label>
				</div>
			</label>

			<label class="flex flex-col gap-1.5">
				<span class="text-dateline">Gemini Model</span>
				<select
					name="aiModel"
					bind:value={aiModel}
					class="w-full rounded-sm border px-3 py-2 text-sm"
					style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
				>
					{#each data.supportedModels ?? SUPPORTED_MODELS as opt}
						<option value={opt.id}>{opt.label}</option>
					{/each}
				</select>
			</label>
		{/if}

		<button
			type="submit"
			class="font-mono-tight mt-2 self-start rounded-sm px-5 py-2.5 text-sm uppercase tracking-wide cursor-pointer"
			style="background-color: var(--color-ink); color: var(--color-paper);"
		>
			Save settings
		</button>
	</form>
</div>
