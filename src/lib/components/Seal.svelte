<script lang="ts">
	/**
	 * The Seal — Quiet Feed's signature mark. A postmark-style stamp that
	 * appears once an edition is sealed, echoing an airmail postmark rather
	 * than a newspaper masthead. Deliberately a little imperfect: a slight
	 * tilt and a faintly irregular ring, like a hand-pressed ink stamp.
	 */
	interface Props {
		issueNumber: number;
		dateLabel: string; // e.g. "16 JUN"
		size?: number;
		tilt?: boolean;
	}

	let { issueNumber, dateLabel, size = 96, tilt = true }: Props = $props();

	const ringText = 'QUIET FEED · DAILY EDITION · QUIET FEED · DAILY EDITION · ';
</script>

<svg
	viewBox="0 0 200 200"
	width={size}
	height={size}
	class={tilt ? 'stamp-tilt' : ''}
	role="img"
	aria-label={`Sealed — Issue No. ${issueNumber}, ${dateLabel}`}
>
	<defs>
		<path id="seal-ring-path" d="M 100,100 m -78,0 a 78,78 0 1,1 156,0 a 78,78 0 1,1 -156,0" />
	</defs>

	<!-- Outer ring: slightly irregular, ink-stamped feel -->
	<circle
		cx="100"
		cy="100"
		r="92"
		fill="none"
		stroke="var(--color-stamp)"
		stroke-width="2.5"
		opacity="0.85"
	/>
	<circle
		cx="100"
		cy="100"
		r="78"
		fill="none"
		stroke="var(--color-stamp)"
		stroke-width="1.25"
		opacity="0.6"
	/>

	<text font-family="var(--font-mono)" font-size="9.5" letter-spacing="2" fill="var(--color-stamp)">
		<textPath href="#seal-ring-path" startOffset="2%">
			{ringText}
		</textPath>
	</text>

	<!-- Center mark -->
	<line x1="58" y1="100" x2="142" y2="100" stroke="var(--color-stamp)" stroke-width="1.5" opacity="0.5" />
	<text
		x="100"
		y="92"
		text-anchor="middle"
		font-family="var(--font-display)"
		font-weight="600"
		font-size="22"
		fill="var(--color-stamp)"
	>
		№ {issueNumber}
	</text>
	<text
		x="100"
		y="116"
		text-anchor="middle"
		font-family="var(--font-mono)"
		font-size="11"
		letter-spacing="1.5"
		fill="var(--color-stamp)"
	>
		{dateLabel}
	</text>
</svg>
