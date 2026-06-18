import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { SvelteKitPWA } from '@vite-pwa/sveltekit';
import { defineConfig } from 'vite';

export default defineConfig({
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
