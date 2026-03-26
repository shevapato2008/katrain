"""Encrypted credentials storage for board mode.

See design.md Section 4.16.
Stores refresh tokens encrypted on disk using device-derived keys.
Falls back to plaintext in ~/.katrain/ if cryptography is not installed.
"""

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("katrain_web")

# Default credentials directory
_CREDENTIALS_DIR = Path.home() / ".katrain" / "credentials"


def _derive_key(device_id: str) -> bytes:
    """Derive a 32-byte encryption key from the device ID using SHA-256."""
    return hashlib.sha256(device_id.encode("utf-8")).digest()


def _get_cred_path(device_id: str) -> Path:
    """Get the credentials file path for a device."""
    safe_id = hashlib.md5(device_id.encode()).hexdigest()[:16]
    return _CREDENTIALS_DIR / f"cred_{safe_id}.enc"


def _encrypt(data: bytes, key: bytes) -> bytes:
    """Encrypt data using Fernet (symmetric encryption).

    Falls back to base64 obfuscation if cryptography is not installed.
    """
    try:
        from cryptography.fernet import Fernet

        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        return f.encrypt(data)
    except ImportError:
        # Fallback: XOR with key + base64 (not secure, but better than plaintext)
        xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return base64.b64encode(xored)


def _decrypt(data: bytes, key: bytes) -> bytes:
    """Decrypt data using Fernet.

    Falls back to base64 de-obfuscation if cryptography is not installed.
    """
    try:
        from cryptography.fernet import Fernet

        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        return f.decrypt(data)
    except ImportError:
        decoded = base64.b64decode(data)
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(decoded))


def save_refresh_token(device_id: str, refresh_token: str) -> bool:
    """Save refresh token to encrypted file."""
    try:
        _CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        key = _derive_key(device_id)
        payload = json.dumps({"refresh_token": refresh_token}).encode("utf-8")
        encrypted = _encrypt(payload, key)
        cred_path = _get_cred_path(device_id)
        cred_path.write_bytes(encrypted)
        # Restrict file permissions (owner only)
        os.chmod(cred_path, 0o600)
        logger.debug(f"Saved credentials to {cred_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save credentials: {e}")
        return False


def load_refresh_token(device_id: str) -> Optional[str]:
    """Load refresh token from encrypted file. Returns None if not found."""
    cred_path = _get_cred_path(device_id)
    if not cred_path.exists():
        return None
    try:
        key = _derive_key(device_id)
        encrypted = cred_path.read_bytes()
        decrypted = _decrypt(encrypted, key)
        data = json.loads(decrypted.decode("utf-8"))
        return data.get("refresh_token")
    except Exception as e:
        logger.warning(f"Failed to load credentials: {e}")
        return None


def delete_credentials(device_id: str) -> bool:
    """Delete stored credentials for a device."""
    cred_path = _get_cred_path(device_id)
    try:
        if cred_path.exists():
            cred_path.unlink()
            logger.debug(f"Deleted credentials: {cred_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete credentials: {e}")
        return False
