import hashlib
import hmac
import secrets
import unicodedata

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def hash_password(password):
    salt = secrets.token_hex(16)
    value = hashlib.scrypt(
        unicodedata.normalize("NFKC", password).encode(),
        salt=salt.encode(),
        n=16384,
        r=16,
        p=1,
        dklen=64,
        maxmem=67108864,
    )
    return f"{salt}:{value.hex()}"


def verify_password(password, stored):
    try:
        salt, expected = stored.split(":")
        if len(salt) != 32 or len(expected) != 128:
            return False
        value = hashlib.scrypt(
            unicodedata.normalize("NFKC", password).encode(),
            salt=salt.encode(),
            n=16384,
            r=16,
            p=1,
            dklen=64,
            maxmem=67108864,
        )
        return hmac.compare_digest(value.hex(), expected)
    except (ValueError, TypeError, AttributeError):
        return False


def sign(value, secret):
    return value + "." + hmac.new(secret.encode(), value.encode(), "sha256").hexdigest()


def unsign(value, secret):
    if not value or "." not in value:
        return None
    token, _ = value.rsplit(".", 1)
    try:
        return token if hmac.compare_digest(value, sign(token, secret)) else None
    except TypeError:
        return None


def encryption_key(config):
    # Match node:crypto.scryptSync's defaults and the original application's salt.
    return hashlib.scrypt(
        (config.encryption_key or config.secret).encode(),
        salt=b"quiet-feed-encryption-salt",
        n=16384,
        r=8,
        p=1,
        dklen=32,
    )


def encrypt_secret(value, config):
    iv = secrets.token_bytes(12)
    encrypted = AESGCM(encryption_key(config)).encrypt(iv, value.encode(), None)
    return f"{iv.hex()}:{encrypted[-16:].hex()}:{encrypted[:-16].hex()}"


def decrypt_secret(value, config):
    try:
        iv, tag, ciphertext = (bytes.fromhex(part) for part in value.split(":"))
        return AESGCM(encryption_key(config)).decrypt(iv, ciphertext + tag, None).decode()
    except Exception:
        return None


def mask_key(value):
    return value[:6] + "••••••••" + value[-4:] if value and len(value) >= 8 else "••••••••"
