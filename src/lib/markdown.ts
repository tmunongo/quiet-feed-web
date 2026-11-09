/**
 * Lightweight, XSS-safe markdown converter tailored for Quiet Feed's "Morning Dispatch" summaries.
 * Escapes untrusted text, validates internal links, and produces clean semantic HTML markup.
 */

export function escapeHtml(str: string): string {
	return str
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#39;');
}

const INTERNAL_LINK_REGEX = /^\/article\/[a-zA-Z0-9_-]+$/;

export function formatInline(text: string): string {
	// 1. Escape all raw untrusted text before applying markdown formatting
	const escaped = escapeHtml(text);

	return escaped
		// Bold: **text**
		.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
		// Italic: *text*
		.replace(/\*(.*?)\*/g, '<em>$1</em>')
		// Markdown Links: [title](url) -> only internal /article/{id} become anchors
		.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_match, title, rawHref) => {
			const href = rawHref.replace(/&amp;/g, '&').trim();
			if (INTERNAL_LINK_REGEX.test(href)) {
				return `<a href="${escapeHtml(href)}" class="underline decoration-dotted hover:decoration-solid" style="color: var(--color-airmail); font-weight: 500;">${title}</a>`;
			}
			// Render external URLs and other non-article links as plain text
			return title;
		});
}

export function renderDispatchMarkdown(md: string): string {
	if (!md) return '';

	// Normalize line breaks
	const rawLines = md.replace(/\r\n/g, '\n').split('\n');
	const out: string[] = [];

	let currentListType: 'ul' | 'ol' | null = null;
	let paragraphBuffer: string[] = [];

	function flushParagraph() {
		if (paragraphBuffer.length > 0) {
			const text = paragraphBuffer.join(' ').trim();
			if (text) {
				out.push(
					`<p class="font-body text-base md:text-lg leading-relaxed mb-5" style="color: var(--color-ink);">${formatInline(
						text
					)}</p>`
				);
			}
			paragraphBuffer = [];
		}
	}

	function closeList() {
		if (currentListType === 'ul') {
			out.push('</ul>');
			currentListType = null;
		} else if (currentListType === 'ol') {
			out.push('</ol>');
			currentListType = null;
		}
	}

	for (let i = 0; i < rawLines.length; i++) {
		const line = rawLines[i].trim();

		// Empty line -> separates blocks
		if (!line) {
			flushParagraph();
			closeList();
			continue;
		}

		// Horizontal rule: --- or *** or ___
		if (/^(?:-{3,}|\*{3,}|_{3,})$/.test(line)) {
			flushParagraph();
			closeList();
			out.push('<hr class="my-8" style="border-color: var(--color-line);" />');
			continue;
		}

		// Normalize headings that might have list prefix like "1. ### The Lead"
		const headingNormalized = line.replace(/^\d+\.\s+(#+)/, '$1');

		// Headings
		if (headingNormalized.startsWith('#### ')) {
			flushParagraph();
			closeList();
			out.push(
				`<h4 class="font-display text-base md:text-lg font-medium mt-6 mb-2" style="color: var(--color-ink);">${formatInline(
					headingNormalized.slice(5)
				)}</h4>`
			);
			continue;
		}

		if (headingNormalized.startsWith('### ')) {
			flushParagraph();
			closeList();
			out.push(
				`<h3 class="font-display text-lg md:text-xl font-semibold mt-8 mb-3" style="color: var(--color-ink);">${formatInline(
					headingNormalized.slice(4)
				)}</h3>`
			);
			continue;
		}

		if (headingNormalized.startsWith('## ')) {
			flushParagraph();
			closeList();
			out.push(
				`<h2 class="font-display text-xl md:text-2xl font-semibold mt-10 mb-3 border-b pb-2" style="color: var(--color-ink); border-color: var(--color-line);">${formatInline(
					headingNormalized.slice(3)
				)}</h2>`
			);
			continue;
		}

		if (headingNormalized.startsWith('# ')) {
			flushParagraph();
			closeList();
			out.push(
				`<h1 class="font-display text-2xl md:text-3xl font-bold mt-10 mb-4 border-b pb-2" style="color: var(--color-ink); border-color: var(--color-line);">${formatInline(
					headingNormalized.slice(2)
				)}</h1>`
			);
			continue;
		}

		// Unordered list (- or *)
		if (/^[-*]\s+/.test(line)) {
			flushParagraph();
			if (currentListType !== 'ul') {
				closeList();
				out.push(
					'<ul class="list-disc pl-5 mb-5 space-y-2 font-body text-base md:text-lg" style="color: var(--color-ink);">'
				);
				currentListType = 'ul';
			}
			const content = line.replace(/^[-*]\s+/, '');
			out.push(`<li>${formatInline(content)}</li>`);
			continue;
		}

		// Ordered list (1. 2. etc.)
		if (/^\d+\.\s+/.test(line)) {
			flushParagraph();
			if (currentListType !== 'ol') {
				closeList();
				out.push(
					'<ol class="list-decimal pl-5 mb-5 space-y-2 font-body text-base md:text-lg" style="color: var(--color-ink);">'
				);
				currentListType = 'ol';
			}
			const content = line.replace(/^\d+\.\s+/, '');
			out.push(`<li>${formatInline(content)}</li>`);
			continue;
		}

		// Blockquote (> )
		if (line.startsWith('>')) {
			flushParagraph();
			closeList();
			const quoteContent = line.replace(/^>\s*/, '');
			out.push(
				`<blockquote class="border-l-2 pl-4 py-1 italic mb-5 font-body text-base md:text-lg" style="border-color: var(--color-line); color: var(--color-ink-soft);">${formatInline(
					quoteContent
				)}</blockquote>`
			);
			continue;
		}

		// Ordinary paragraph line: accumulate into current paragraph buffer
		paragraphBuffer.push(line);
	}

	flushParagraph();
	closeList();

	return out.join('\n');
}
