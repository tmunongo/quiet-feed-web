import { betterAuth } from 'better-auth';
import { drizzleAdapter } from 'better-auth/adapters/drizzle';
import { sveltekitCookies } from 'better-auth/svelte-kit';
import { getRequestEvent } from '$app/server';
import { db } from './db';
import * as schema from './db/schema';
import { userSettings } from './db/schema';

const SECURE_COOKIES = process.env.SECURE_COOKIES === 'true';

export const auth = betterAuth({
	appName: 'Quiet Feed',
	baseURL: process.env.BETTER_AUTH_URL ?? 'http://localhost:3000',
	secret: process.env.BETTER_AUTH_SECRET,
	database: drizzleAdapter(db, {
		provider: 'sqlite',
		schema
	}),
	emailAndPassword: {
		enabled: true,
		minPasswordLength: 8,
		// Quiet Feed is currently a self/small-hosted service with no mail
		// sending configured. Flip this on once an email provider is wired
		// up via the `sendResetPassword` option below.
		requireEmailVerification: false
	},
	session: {
		// 30 days, refreshed if less than 15 days remain — matches the
		// "set it and forget it" feel the rest of the app goes for.
		expiresIn: 60 * 60 * 24 * 30,
		updateAge: 60 * 60 * 24 * 15
	},
	advanced: {
		useSecureCookies: SECURE_COOKIES
	},
	databaseHooks: {
		user: {
			create: {
				after: async (user) => {
					// Every Quiet Feed account needs a settings row (edition
					// time, timezone, theme, habits mode) the moment it
					// exists, so the rest of the app can assume it's there.
					await db.insert(userSettings).values({ userId: user.id });
				}
			}
		}
	},
	plugins: [sveltekitCookies(getRequestEvent)]
});

export type Auth = typeof auth;
