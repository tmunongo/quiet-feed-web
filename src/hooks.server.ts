import type { Handle } from '@sveltejs/kit';
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
	const session = await auth.api.getSession({ headers: event.request.headers });

	if (session) {
		event.locals.user = session.user;
		event.locals.session = session.session;
	} else {
		event.locals.user = null;
		event.locals.session = null;
	}

	return svelteKitHandler({ event, resolve, auth, building });
};
