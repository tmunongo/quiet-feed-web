import { createCipheriv, createDecipheriv, randomBytes, scryptSync } from 'node:crypto';

const ALGORITHM = 'aes-256-gcm';
const IV_LENGTH = 12; // Standard for GCM
const SALT = 'quiet-feed-encryption-salt';

let cachedKey: Buffer | null = null;

function getEncryptionKey(): Buffer {
	if (cachedKey) return cachedKey;

	const secret = process.env.ENCRYPTION_KEY || process.env.BETTER_AUTH_SECRET;
	if (!secret) {
		throw new Error('ENCRYPTION_KEY or BETTER_AUTH_SECRET must be configured in environment.');
	}

	cachedKey = scryptSync(secret, SALT, 32);
	return cachedKey;
}

/**
 * Encrypts a plain text string using AES-256-GCM.
 * Output format: iv:authTag:ciphertext (hex encoded)
 */
export function encryptSecret(plainText: string): string {
	const key = getEncryptionKey();
	const iv = randomBytes(IV_LENGTH);
	const cipher = createCipheriv(ALGORITHM, key, iv);

	let encrypted = cipher.update(plainText, 'utf8', 'hex');
	encrypted += cipher.final('hex');

	const authTag = cipher.getAuthTag();

	return `${iv.toString('hex')}:${authTag.toString('hex')}:${encrypted}`;
}

/**
 * Decrypts an encrypted string created by `encryptSecret`.
 * Returns null if decryption fails (e.g. invalid key or corrupted data).
 */
export function decryptSecret(encryptedPayload: string): string | null {
	try {
		const parts = encryptedPayload.split(':');
		if (parts.length !== 3) return null;

		const [ivHex, tagHex, cipherHex] = parts;
		const key = getEncryptionKey();
		const iv = Buffer.from(ivHex, 'hex');
		const authTag = Buffer.from(tagHex, 'hex');

		const decipher = createDecipheriv(ALGORITHM, key, iv);
		decipher.setAuthTag(authTag);

		let decrypted = decipher.update(cipherHex, 'hex', 'utf8');
		decrypted += decipher.final('utf8');

		return decrypted;
	} catch {
		return null;
	}
}

/**
 * Helper to mask an API key for safe display in UI (e.g. "AIzaSy...4xK9")
 */
export function maskApiKey(key: string): string {
	if (!key || key.length < 8) return '••••••••';
	return `${key.slice(0, 6)}••••••••${key.slice(-4)}`;
}

