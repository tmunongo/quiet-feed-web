import { error, redirect } from '@sveltejs/kit';
import { eq, desc } from 'drizzle-orm';
import { db } from '$lib/server/db';
import { editionArticles, articles, feeds, editions } from '$lib/server/db/schema';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, locals }) => {
	if (!locals.user) {
		throw redirect(302, '/login');
	}

	const [row] = await db
		.select({
			editionArticleId: editionArticles.id,
			scrollPercent: editionArticles.scrollPercent,
			scrollOffset: editionArticles.scrollOffset,
			read: editionArticles.read,
			articleId: articles.id,
			title: articles.title,
			url: articles.url,
			author: articles.author,
			contentHtml: articles.contentHtml,
			excerpt: articles.excerpt,
			publishedAt: articles.publishedAt,
			feedTitle: feeds.title,
			feedId: feeds.id,
			editionUserId: editions.userId,
			editionDate: editions.date,
			issueNumber: editions.issueNumber
		})
		.from(editionArticles)
		.innerJoin(articles, eq(editionArticles.articleId, articles.id))
		.innerJoin(feeds, eq(articles.feedId, feeds.id))
		.innerJoin(editions, eq(editionArticles.editionId, editions.id))
		.where(eq(editionArticles.id, params.id))
		.limit(1);

	if (!row || row.editionUserId !== locals.user.id) {
		throw error(404, 'Article not found');
	}

	const [latestEdition] = await db
		.select({ date: editions.date })
		.from(editions)
		.where(eq(editions.userId, locals.user.id))
		.orderBy(desc(editions.date))
		.limit(1);

	const isLatest = latestEdition && latestEdition.date === row.editionDate;
	const backUrl = isLatest ? '/' : `/archive/${row.editionDate}`;

	return {
		editionArticleId: row.editionArticleId,
		title: row.title,
		url: row.url,
		author: row.author,
		contentHtml: row.contentHtml,
		excerpt: row.excerpt,
		publishedAt: row.publishedAt,
		feedTitle: row.feedTitle,
		read: row.read,
		scrollPercent: row.scrollPercent,
		scrollOffset: row.scrollOffset,
		issueNumber: row.issueNumber,
		backUrl
	};
};
