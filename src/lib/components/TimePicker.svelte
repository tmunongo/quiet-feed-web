<script lang="ts">
	let { value = $bindable('07:00'), name = 'editionTime' } = $props();

	let isOpen = $state(false);
	let containerEl: HTMLDivElement | null = $state(null);
	let hourEl: HTMLDivElement | null = $state(null);
	let minuteEl: HTMLDivElement | null = $state(null);

	const itemHeight = 40; // height in pixels of each reel item

	const hours = Array.from({ length: 24 }, (_, i) => i);
	const minutes = Array.from({ length: 60 }, (_, i) => i);

	// Parse current hour and minute from value
	let currentHour = $state(7);
	let currentMinute = $state(0);

	// Update local state when value changes (e.g. from outside or on initialization)
	$effect(() => {
		const parts = value.split(':');
		const h = parseInt(parts[0] || '7', 10);
		const m = parseInt(parts[1] || '0', 10);
		if (!isNaN(h) && h >= 0 && h < 24) currentHour = h;
		if (!isNaN(m) && m >= 0 && m < 60) currentMinute = m;
	});

	// Flag to prevent scroll events from firing during programmatic scrolling
	let isScrollingProgrammatically = false;

	function toggleDropdown(event: MouseEvent) {
		event.stopPropagation();
		isOpen = !isOpen;
	}

	function closeDropdown() {
		isOpen = false;
	}

	function selectHour(h: number) {
		currentHour = h;
		updateValue();
		scrollToHour(h);
	}

	function selectMinute(m: number) {
		currentMinute = m;
		updateValue();
		scrollToMinute(m);
	}

	function scrollToHour(h: number, behavior: ScrollBehavior = 'smooth') {
		if (!hourEl) return;
		isScrollingProgrammatically = true;
		hourEl.scrollTo({ top: h * itemHeight, behavior });
		setTimeout(() => {
			isScrollingProgrammatically = false;
		}, 300);
	}

	function scrollToMinute(m: number, behavior: ScrollBehavior = 'smooth') {
		if (!minuteEl) return;
		isScrollingProgrammatically = true;
		minuteEl.scrollTo({ top: m * itemHeight, behavior });
		setTimeout(() => {
			isScrollingProgrammatically = false;
		}, 300);
	}

	function updateValue() {
		const hStr = String(currentHour).padStart(2, '0');
		const mStr = String(currentMinute).padStart(2, '0');
		value = `${hStr}:${mStr}`;
	}

	let hourScrollTimeout: any;
	function handleHourScroll() {
		if (isScrollingProgrammatically || !hourEl) return;
		clearTimeout(hourScrollTimeout);
		hourScrollTimeout = setTimeout(() => {
			if (!hourEl) return;
			const idx = Math.round(hourEl.scrollTop / itemHeight);
			if (idx >= 0 && idx < 24 && idx !== currentHour) {
				currentHour = idx;
				updateValue();
			}
		}, 50);
	}

	let minuteScrollTimeout: any;
	function handleMinuteScroll() {
		if (isScrollingProgrammatically || !minuteEl) return;
		clearTimeout(minuteScrollTimeout);
		minuteScrollTimeout = setTimeout(() => {
			if (!minuteEl) return;
			const idx = Math.round(minuteEl.scrollTop / itemHeight);
			if (idx >= 0 && idx < 60 && idx !== currentMinute) {
				currentMinute = idx;
				updateValue();
			}
		}, 50);
	}

	function handleHourKeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowUp') {
			event.preventDefault();
			const nextHour = (currentHour - 1 + 24) % 24;
			selectHour(nextHour);
		} else if (event.key === 'ArrowDown') {
			event.preventDefault();
			const nextHour = (currentHour + 1) % 24;
			selectHour(nextHour);
		} else if (event.key === 'Enter' || event.key === 'Escape') {
			event.preventDefault();
			closeDropdown();
		}
	}

	function handleMinuteKeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowUp') {
			event.preventDefault();
			const nextMinute = (currentMinute - 1 + 60) % 60;
			selectMinute(nextMinute);
		} else if (event.key === 'ArrowDown') {
			event.preventDefault();
			const nextMinute = (currentMinute + 1) % 60;
			selectMinute(nextMinute);
		} else if (event.key === 'Enter' || event.key === 'Escape') {
			event.preventDefault();
			closeDropdown();
		}
	}

	// Scroll the reels to match current state when dropdown opens
	$effect(() => {
		if (isOpen) {
			setTimeout(() => {
				scrollToHour(currentHour, 'instant');
				scrollToMinute(currentMinute, 'instant');
			}, 0);
		}
	});

	// Click outside detection
	function handleClickOutside(event: MouseEvent) {
		if (isOpen && containerEl && !containerEl.contains(event.target as Node)) {
			closeDropdown();
		}
	}
</script>

<svelte:window onclick={handleClickOutside} />

<div class="relative inline-block w-40" bind:this={containerEl}>
	<button
		type="button"
		onclick={toggleDropdown}
		class="w-full font-mono text-sm px-3 py-2 border rounded-sm flex items-center justify-between select-none cursor-pointer"
		style="background-color: var(--color-paper-raised); border-color: var(--color-line); color: var(--color-ink);"
		aria-haspopup="dialog"
		aria-expanded={isOpen}
	>
		<div class="flex items-center gap-2">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				width="16"
				height="16"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				class="w-4 h-4 text-[var(--color-ink-faint)]"
			>
				<circle cx="12" cy="12" r="10" />
				<polyline points="12 6 12 12 16 14" />
			</svg>
			<span>{value}</span>
		</div>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			width="16"
			height="16"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="2"
			stroke-linecap="round"
			stroke-linejoin="round"
			class="w-3.5 h-3.5 text-[var(--color-ink-faint)] transition-transform duration-200"
			style="transform: {isOpen ? 'rotate(180deg)' : 'none'};"
		>
			<polyline points="6 9 12 15 18 9" />
		</svg>
	</button>

	<!-- Hidden input to submit the value in standard forms -->
	<input type="hidden" {name} {value} />

	{#if isOpen}
		<div
			class="absolute left-0 mt-1 z-50 rounded-sm border shadow-lg flex flex-col p-4 w-60 gap-4"
			style="background-color: var(--color-paper-raised); border-color: var(--color-line); border-radius: 2px;"
			role="dialog"
			aria-label="Time picker"
		>
			<div class="flex items-center justify-center gap-2 relative">
				<!-- Lens overlay centered in the container -->
				<div class="selection-lens"></div>

				<!-- Hours Reel -->
				<div class="reel-container">
					<div class="fade-overlay fade-top"></div>
					<div class="fade-overlay fade-bottom"></div>
					<div
						bind:this={hourEl}
						onscroll={handleHourScroll}
						onkeydown={handleHourKeydown}
						class="reel scrollbar-none"
						tabindex="0"
						role="listbox"
						aria-label="Hour selector (use up/down keys)"
					>
						{#each hours as h}
							<button
								type="button"
								tabindex="-1"
								onclick={() => selectHour(h)}
								class="reel-item {currentHour === h ? 'selected' : ''}"
								role="option"
								aria-selected={currentHour === h}
							>
								{String(h).padStart(2, '0')}
							</button>
						{/each}
					</div>
				</div>

				<span class="font-mono text-xl select-none text-[var(--color-ink-faint)]">:</span>

				<!-- Minutes Reel -->
				<div class="reel-container">
					<div class="fade-overlay fade-top"></div>
					<div class="fade-overlay fade-bottom"></div>
					<div
						bind:this={minuteEl}
						onscroll={handleMinuteScroll}
						onkeydown={handleMinuteKeydown}
						class="reel scrollbar-none"
						tabindex="0"
						role="listbox"
						aria-label="Minute selector (use up/down keys)"
					>
						{#each minutes as m}
							<button
								type="button"
								tabindex="-1"
								onclick={() => selectMinute(m)}
								class="reel-item {currentMinute === m ? 'selected' : ''}"
								role="option"
								aria-selected={currentMinute === m}
							>
								{String(m).padStart(2, '0')}
							</button>
						{/each}
					</div>
				</div>
			</div>

			<div class="flex justify-between items-center border-t pt-3" style="border-color: var(--color-line);">
				<span class="font-mono text-xs text-[var(--color-ink-faint)]">
					Press Enter to close
				</span>
				<button
					type="button"
					onclick={closeDropdown}
					class="font-mono-tight px-3 py-1.5 text-xs uppercase tracking-wide rounded-sm cursor-pointer"
					style="background-color: var(--color-ink); color: var(--color-paper);"
				>
					Done
				</button>
			</div>
		</div>
	{/if}
</div>

<style>
	.reel-container {
		position: relative;
		width: 60px;
		height: 200px;
	}

	.reel {
		height: 200px;
		overflow-y: scroll;
		scroll-snap-type: y mandatory;
		padding-top: 80px;
		padding-bottom: 80px;
		box-sizing: border-box;
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	/* Hide scrollbars */
	.scrollbar-none {
		-ms-overflow-style: none; /* IE and Edge */
		scrollbar-width: none; /* Firefox */
	}
	.scrollbar-none::-webkit-scrollbar {
		display: none; /* Chrome, Safari and Opera */
	}

	.reel-item {
		height: 40px;
		width: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		scroll-snap-align: center;
		font-family: var(--font-mono);
		font-size: 1.1rem;
		color: var(--color-ink-soft);
		cursor: pointer;
		background: none;
		border: none;
		padding: 0;
		outline: none;
		transition: color 0.15s ease, font-weight 0.15s ease;
	}

	.reel-item.selected {
		color: var(--color-airmail);
		font-weight: 600;
	}

	.selection-lens {
		position: absolute;
		top: 80px;
		left: 0;
		right: 0;
		height: 40px;
		border-top: 1.5px solid var(--color-line);
		border-bottom: 1.5px solid var(--color-line);
		background-color: rgba(42, 74, 107, 0.06); /* very soft airmail blue tint */
		pointer-events: none;
	}

	.fade-overlay {
		position: absolute;
		left: 0;
		right: 0;
		height: 80px;
		pointer-events: none;
		z-index: 10;
	}

	.fade-top {
		top: 0;
		background: linear-gradient(to bottom, var(--color-paper-raised) 0%, transparent 100%);
	}

	.fade-bottom {
		bottom: 0;
		background: linear-gradient(to top, var(--color-paper-raised) 0%, transparent 100%);
	}
</style>
