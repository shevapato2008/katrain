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
MAX_PENDING_PER_IP = 5
MAX_BODY_BYTES = 4096


def _trusted_proxies():
    import ipaddress
    import os

    raw = os.getenv("KATRAIN_TRUSTED_PROXIES", "127.0.0.1/32,::1/128,172.16.0.0/12")
    return [ipaddress.ip_network(part.strip(), strict=False) for part in raw.split(",") if part.strip()]


def client_ip(request) -> str | None:
    """The peer address, or the proxy-reported one only when the peer is a trusted proxy
    (nginx on the host reaches the container through the docker bridge)."""
    import ipaddress

    peer = request.client.host if request.client else None
    if peer is None:
        return None
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return peer[:64]
    if any(peer_ip in net for net in _trusted_proxies()):
        forwarded = request.headers.get("x-real-ip") or (request.headers.get("x-forwarded-for") or "").split(",")[-1].strip()
        if forwarded:
            try:
                return str(ipaddress.ip_address(forwarded))
            except ValueError:
                pass
    return str(peer_ip)


def signature(key_hex: str, timestamp: str, body: bytes) -> str:
    return hmac.new(bytes.fromhex(key_hex), timestamp.encode() + b"\n" + body, hashlib.sha256).hexdigest()


def valid_signature(key_hex: str, timestamp: str, body: bytes, claimed: str) -> bool:
    try:
        return hmac.compare_digest(signature(key_hex, timestamp, body), claimed.lower())
    except (ValueError, AttributeError):
        return False
