// Assembles a frozen edition into the shape the reading UI wants: articles
// grouped by feed category, in the order they were frozen, each carrying
// its own read/scroll-progress state.
import { eq, asc } from 'drizzle-orm';
import { db } from '../db';
import { articles, editionArticles, editions, feeds } from '../db/schema';

export interface EditionArticleView {
	editionArticleId: string;
	articleId: string;
	title: string;
	url: string;
	author: string | null;
	excerpt: string | null;
	publishedAt: Date | null;
	feedTitle: string;
	feedId: string;
	read: boolean;
	scrollPercent: number;
}

export interface EditionCategoryView {
	category: string;
	articles: EditionArticleView[];
}

export interface EditionView {
	id: string;
	date: string;
	issueNumber: number;
	categories: EditionCategoryView[];
	totalCount: number;
	readCount: number;
}

export async function getEditionView(editionId: string): Promise<EditionView | null> {
	const [edition] = await db.select().from(editions).where(eq(editions.id, editionId)).limit(1);
	if (!edition) return null;

	const rows = await db
		.select({
			editionArticleId: editionArticles.id,
			articleId: articles.id,
			title: articles.title,
			url: articles.url,
			author: articles.author,
			excerpt: articles.excerpt,
			publishedAt: articles.publishedAt,
			read: editionArticles.read,
			scrollPercent: editionArticles.scrollPercent,
			feedId: feeds.id,
			feedTitle: feeds.title,
			category: feeds.category
		})
		.from(editionArticles)
		.innerJoin(articles, eq(editionArticles.articleId, articles.id))
		.innerJoin(feeds, eq(articles.feedId, feeds.id))
		.where(eq(editionArticles.editionId, editionId))
		.orderBy(asc(editionArticles.position));

	const byCategory = new Map<string, EditionArticleView[]>();
	let readCount = 0;

	for (const row of rows) {
		if (row.read) readCount++;
		const entry: EditionArticleView = {
			editionArticleId: row.editionArticleId,
			articleId: row.articleId,
			title: row.title,
			url: row.url,
			author: row.author,
			excerpt: row.excerpt,
			publishedAt: row.publishedAt,
			feedTitle: row.feedTitle,
			feedId: row.feedId,
			read: row.read,
			scrollPercent: row.scrollPercent
		};
		const list = byCategory.get(row.category) ?? [];
		list.push(entry);
		byCategory.set(row.category, list);
	}

	const categories: EditionCategoryView[] = Array.from(byCategory.entries())
		.sort(([a], [b]) => a.localeCompare(b))
		.map(([category, articleList]) => ({ category, articles: articleList }));

	return {
		id: edition.id,
		date: edition.date,
		issueNumber: edition.issueNumber,
		categories,
		totalCount: rows.length,
		readCount
	};
}
