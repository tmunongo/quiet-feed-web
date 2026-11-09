CREATE TABLE `edition_summaries` (
	`id` text PRIMARY KEY NOT NULL,
	`edition_id` text NOT NULL,
	`content_markdown` text NOT NULL,
	`model` text NOT NULL,
	`prompt_tokens` integer,
	`completion_tokens` integer,
	`status` text DEFAULT 'completed' NOT NULL,
	`error_message` text,
	`created_at` integer NOT NULL,
	FOREIGN KEY (`edition_id`) REFERENCES `editions`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE UNIQUE INDEX `edition_summaries_edition_id_unique` ON `edition_summaries` (`edition_id`);--> statement-breakpoint
ALTER TABLE `user_settings` ADD `gemini_api_key` text;--> statement-breakpoint
ALTER TABLE `user_settings` ADD `ai_model` text DEFAULT 'gemini-3.6-flash' NOT NULL;--> statement-breakpoint
ALTER TABLE `user_settings` ADD `ai_digest_enabled` integer DEFAULT false NOT NULL;--> statement-breakpoint
ALTER TABLE `user_settings` ADD `ai_digest_trigger` text DEFAULT 'manual' NOT NULL;