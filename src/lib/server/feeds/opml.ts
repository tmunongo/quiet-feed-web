// Minimal OPML 2.0 import/export — just enough to round-trip with Feedly,
// NetNewsWire, Inoreader, and friends, which all use the same flat
// "outline" structure: a top-level <outline> per category containing
// <outline type="rss"> leaves per feed.
import { XMLParser } from 'fast-xml-parser';

export interface ParsedOpmlFeed {
	title: string;
	url: string;
	category: string;
}

function asArray<T>(value: T | T[] | undefined): T[] {
	if (value === undefined) return [];
	return Array.isArray(value) ? value : [value];
}

export function parseOpml(xml: string): ParsedOpmlFeed[] {
	const parser = new XMLParser({ ignoreAttributes: false, attributeNamePrefix: '@_' });
	const doc = parser.parse(xml);

	const body = doc?.opml?.body;
	if (!body) return [];

	const results: ParsedOpmlFeed[] = [];

	function walk(outline: Record<string, unknown>, category: string) {
		const xmlUrl = outline['@_xmlUrl'] as string | undefined;

		if (xmlUrl) {
			results.push({
				title: (outline['@_title'] || outline['@_text'] || xmlUrl) as string,
				url: xmlUrl,
				category
			});
			return;
		}

		// A category folder: no xmlUrl of its own, just nested outlines.
		const nextCategory = (outline['@_title'] || outline['@_text'] || category) as string;
		for (const child of asArray(outline.outline as Record<string, unknown> | Record<string, unknown>[])) {
			walk(child, nextCategory);
		}
	}

	for (const topLevel of asArray(body.outline as Record<string, unknown> | Record<string, unknown>[])) {
		walk(topLevel, 'General');
	}

	return results;
}

function escapeXml(value: string): string {
	return value
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;');
}

export function buildOpml(feedsByCategory: Map<string, ParsedOpmlFeed[]>): string {
	const categoryBlocks = Array.from(feedsByCategory.entries())
		.map(([category, feeds]) => {
			const leaves = feeds
				.map(
					(f) =>
						`			<outline type="rss" text="${escapeXml(f.title)}" title="${escapeXml(f.title)}" xmlUrl="${escapeXml(f.url)}" />`
				)
				.join('\n');
			return `		<outline text="${escapeXml(category)}" title="${escapeXml(category)}">\n${leaves}\n		</outline>`;
		})
		.join('\n');

	return `<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
	<head>
		<title>Quiet Feed subscriptions</title>
	</head>
	<body>
${categoryBlocks}
	</body>
</opml>
`;
}
