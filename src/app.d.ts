import type { auth } from '$lib/server/auth';

type Session = Awaited<ReturnType<typeof auth.api.getSession>>;

declare global {
	namespace App {
		interface Locals {
			user: NonNullable<Session>['user'] | null;
			session: NonNullable<Session>['session'] | null;
		}
		// interface Error {}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
