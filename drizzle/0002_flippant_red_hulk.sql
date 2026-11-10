ALTER TABLE `editions` ADD `closed_at` integer;--> statement-breakpoint
ALTER TABLE `user_settings` ADD `edition_article_cap` integer DEFAULT 20 NOT NULL;