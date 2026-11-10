import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { SvelteKitPWA } from '@vite-pwa/sveltekit';
import { defineConfig } from 'vite';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

// Vite 5 tracks bun.lockb but not Bun’s text lockfile. Give each dependency
// set its own cache so a new Svelte compiler cannot reuse an older runtime.
const dependencyHash = createHash('sha256')
	.update(readFileSync(new URL('./bun.lock', import.meta.url)))
	.digest('hex')
	.slice(0, 16);

export default defineConfig({
	cacheDir: `node_modules/.vite/${dependencyHash}`,
	plugins: [
		tailwindcss(),
		sveltekit(),
		SvelteKitPWA({
			registerType: 'autoUpdate',
			injectRegister: 'auto',
			manifest: {
				name: 'Quiet Feed',
				short_name: 'Quiet Feed',
				description: 'One edition a day. No infinite scroll, no badges, no noise.',
				start_url: '/',
				scope: '/',
				display: 'standalone',
				background_color: '#ECE7DA',
				theme_color: '#23344D',
				icons: [
					{ src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
					{ src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
					{
						src: '/icons/icon-maskable-512.png',
						sizes: '512x512',
						type: 'image/png',
						purpose: 'maskable'
					}
				]
			},
			workbox: {
				navigateFallback: '/offline',
				navigateFallbackDenylist: [/^\/api/, /^\/feeds/, /^\/settings/, /^\/login/, /^\/register/],
				runtimeCaching: [
					{
						urlPattern: /^\/(article\/.*)?$/,
						handler: 'NetworkFirst',
						method: 'GET',
						options: {
							cacheName: 'edition-cache',
							networkTimeoutSeconds: 4,
							expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 7 }
						}
					}
				]
			},
			devOptions: {
				enabled: false
			}
		})
	]
});
