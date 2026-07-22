import { execSync } from 'node:child_process';
import pkg from '../../../package.json';

function getCommitHash(): string {
	if (process.env.COMMIT_HASH) {
		return process.env.COMMIT_HASH.slice(0, 7);
	}
	try {
		return execSync('git rev-parse --short HEAD').toString().trim();
	} catch {
		return 'unknown';
	}
}

function getVersion(): string {
	const raw = process.env.APP_VERSION || pkg.version;
	return raw.replace(/^v/, '');
}

export const appInfo = {
	version: getVersion(),
	commitHash: getCommitHash(),
	repoUrl: process.env.REPO_URL || 'https://github.com/tmunongo/quiet-feed-web'
};
