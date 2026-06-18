// Optional in-process scheduler. Every 10 minutes, checks every user's
// configured edition time against their timezone and compiles a fresh
// edition for anyone who's due and doesn't have one yet.
//
// This exists alongside, not instead of, the on-open fallback in
// getOrCompileTodaysEdition() — that fallback is what guarantees an edition
// shows up even if this scheduler was never started (e.g. multiple server
// instances behind a load balancer, where you'd disable this in favor of an
// external cron hitting /api/cron/compile on a single instance instead).
import { db } from './db';
import { userSettings } from './db/schema';
import { isEditionDue, compileEdition } from './edition/compiler';

const CHECK_INTERVAL_MS = 10 * 60 * 1000;

let started = false;

export function startScheduler() {
	if (started) return;
	if (process.env.ENABLE_INTERNAL_SCHEDULER !== 'true') return;
	started = true;

	const tick = async () => {
		try {
			const allSettings = await db.select({ userId: userSettings.userId }).from(userSettings);
			for (const { userId } of allSettings) {
				try {
					if (await isEditionDue(userId)) {
						const { articleCount } = await compileEdition(userId);
						console.log(`[scheduler] compiled edition for user ${userId} (${articleCount} articles)`);
					}
				} catch (err) {
					console.error(`[scheduler] failed to compile edition for user ${userId}`, err);
				}
			}
		} catch (err) {
			console.error('[scheduler] tick failed', err);
		}
	};

	// Run once shortly after boot, then on the interval.
	setTimeout(tick, 15_000);
	setInterval(tick, CHECK_INTERVAL_MS);
}
