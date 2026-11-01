"""
trafficking/encryption.py

Field-level encryption for sensitive trafficking report data
(reporter_contact field only).

Uses Fernet symmetric encryption from the `cryptography` package.
The key is stored in the TRAFFICKING_ENCRYPTION_KEY environment variable.

If the key is not set, data is stored unencrypted — the field will
still work, just without encryption. This allows the system to
function in development without secrets configured.

Usage:
    from trafficking.encryption import encrypt_field, decrypt_field

    # Encrypt before saving
    report.reporter_contact = encrypt_field(raw_contact)

    # Decrypt when reading
    raw_contact = decrypt_field(report.reporter_contact)

Generating a key (run once, store in Render env vars):
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import os
import base64
import logging

logger = logging.getLogger(__name__)

# Prefix to identify encrypted values (prevents double-encryption)
_ENC_PREFIX = 'ENC:'


def _get_fernet():
    """
    Return a Fernet instance using TRAFFICKING_ENCRYPTION_KEY env var.
    Returns None if key is not configured.
    """
    key = os.getenv('TRAFFICKING_ENCRYPTION_KEY', '').strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        # Fernet requires exactly 32 bytes URL-safe base64 encoded key
        return Fernet(key.encode())
    except Exception as e:
        logger.warning(f"[TIP] Encryption key invalid: {e} — storing unencrypted")
        return None


def encrypt_field(plaintext: str) -> str:
    """
    Encrypt a string. Returns 'ENC:<base64>' or the original
    string if encryption is not configured.
    """
    if not plaintext:
        return plaintext

    # Already encrypted — don't double-encrypt
    if plaintext.startswith(_ENC_PREFIX):
        return plaintext

    fernet = _get_fernet()
    if fernet is None:
        # No key configured — store as-is (dev mode)
        return plaintext

    try:
        encrypted = fernet.encrypt(plaintext.encode())
        return _ENC_PREFIX + base64.urlsafe_b64encode(encrypted).decode()
    except Exception as e:
        logger.warning(f"[TIP] Encryption failed: {e} — storing unencrypted")
        return plaintext


def decrypt_field(stored: str) -> str:
    """
    Decrypt a stored value. Returns the plaintext string.
    Handles both encrypted ('ENC:...') and unencrypted values gracefully.
    """
    if not stored:
        return stored

    # Not encrypted — return as-is
    if not stored.startswith(_ENC_PREFIX):
        return stored

    fernet = _get_fernet()
    if fernet is None:
        logger.warning("[TIP] Cannot decrypt: TRAFFICKING_ENCRYPTION_KEY not set")
        return '[Contact encrypted — key not configured]'

    try:
        encoded = stored[len(_ENC_PREFIX):]
        encrypted = base64.urlsafe_b64decode(encoded.encode())
        return fernet.decrypt(encrypted).decode()
    except Exception as e:
        logger.warning(f"[TIP] Decryption failed: {e}")
        return '[Contact decryption failed]'


def is_encrypted(value: str) -> bool:
    """Check if a stored value is encrypted."""
    return bool(value and value.startswith(_ENC_PREFIX))
