import { createAuthClient } from 'better-auth/svelte';

export const authClient = createAuthClient({
	// Empty baseURL lets the client default to same-origin, which is what
	// we want both in dev (vite) and once this is deployed behind a reverse
	// proxy on a single domain.
	baseURL: ''
});

export const { signIn, signUp, signOut, useSession } = authClient;
