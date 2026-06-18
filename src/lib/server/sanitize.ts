// Feed content is untrusted HTML from arbitrary third-party publishers.
// Sanitize once, at ingestion time, rather than trusting it at render time
// with {@html ...}. Allows the formatting tags articles actually use, drops
// scripts/styles/event handlers/iframes.
import sanitizeHtml from 'sanitize-html';

export function sanitizeArticleHtml(html: string | null | undefined): string | null {
	if (!html) return null;

	return sanitizeHtml(html, {
		allowedTags: [
			'p',
			'br',
			'b',
			'i',
			'em',
			'strong',
			'a',
			'ul',
			'ol',
			'li',
			'blockquote',
			'h1',
			'h2',
			'h3',
			'h4',
			'img',
			'figure',
			'figcaption',
			'pre',
			'code',
			'hr',
			'table',
			'thead',
			'tbody',
			'tr',
			'th',
			'td'
		],
		allowedAttributes: {
			a: ['href', 'title', 'target', 'rel'],
			img: ['src', 'alt', 'title', 'width', 'height', 'loading'],
			'*': ['class']
		},
		allowedSchemes: ['http', 'https', 'mailto'],
		transformTags: {
			a: sanitizeHtml.simpleTransform('a', { target: '_blank', rel: 'noopener noreferrer' })
		}
	});
}
