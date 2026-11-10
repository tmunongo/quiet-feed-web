import type { Handle, HandleServerError } from '@sveltejs/kit';
import { svelteKitHandler } from 'better-auth/svelte-kit';
import { building } from '$app/environment';
import { auth } from '$lib/server/auth';
import { startScheduler } from '$lib/server/scheduler';

if (!building) {
	// Fires once when the server boots. No-ops if ENABLE_INTERNAL_SCHEDULER
	// is not "true" — see .env.example for why you'd turn this off.
	startScheduler();
}

export const handle: Handle = async ({ event, resolve }) => {
	const started = Date.now();
	let status = 500;
	try {
		const session = await auth.api.getSession({ headers: event.request.headers });

		if (session) {
			event.locals.user = session.user;
			event.locals.session = session.session;
		} else {
			event.locals.user = null;
			event.locals.session = null;
		}

		const response = await svelteKitHandler({ event, resolve, auth, building });
		status = response.status;
		return response;
	} finally {
		// Omit query strings, headers and bodies: they can contain credentials or personal data.
		console.log(`[request] ${event.request.method} ${event.url.pathname} ${status} ${Date.now() - started}ms`);
	}
};

export const handleError: HandleServerError = ({ error, event, status }) => {
	console.error(`[request] ${event.request.method} ${event.url.pathname} ${status} failed`, error);
};
