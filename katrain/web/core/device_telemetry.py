"""Signed box telemetry (shared by the public endpoint, the admin page and tests).

The box derives `K = HMAC-SHA256(device_secret, KEY_CONTEXT)` from its factory secret and
registers K once (trust on first use, pending until an admin approves). A heartbeat carries
`X-Device-Timestamp` (unix seconds, within MAX_SKEW_S of the server and strictly greater than the
last accepted one, so a captured request cannot be replayed) and
`X-Device-Signature = HMAC-SHA256(K, "<timestamp>\\n" + body)`.
"""

import hashlib
import hmac

KEY_CONTEXT = b"katrain-device-telemetry/v1"
MAX_SKEW_S = 300
MAX_PENDING = 100
PENDING_TTL_S = 7 * 86400
ONLINE_WITHIN_S = 15 * 60  # three 5-minute report periods


def signature(key_hex: str, timestamp: str, body: bytes) -> str:
    return hmac.new(bytes.fromhex(key_hex), timestamp.encode() + b"\n" + body, hashlib.sha256).hexdigest()


def valid_signature(key_hex: str, timestamp: str, body: bytes, claimed: str) -> bool:
    try:
        return hmac.compare_digest(signature(key_hex, timestamp, body), claimed.lower())
    except (ValueError, AttributeError):
        return False
