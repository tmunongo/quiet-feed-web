import { eq } from 'drizzle-orm';
import { db } from './index';
import { userSettings, type UserSettings } from './schema';

/**
 * Returns the user's settings row, creating a default one first if it
 * doesn't exist yet. Better Auth's databaseHooks.user.create.after is what
 * normally provisions this row the moment an account is created, but
 * reading through this helper everywhere settings are needed means a
 * missing row (hook API drift across versions, manual DB edits, etc.)
 * self-heals instead of throwing.
 */
export async function getOrCreateUserSettings(userId: string): Promise<UserSettings> {
	const [existing] = await db.select().from(userSettings).where(eq(userSettings.userId, userId)).limit(1);
	if (existing) return existing;

	await db.insert(userSettings).values({ userId }).onConflictDoNothing();

	const [created] = await db.select().from(userSettings).where(eq(userSettings.userId, userId)).limit(1);
	return created;
}
