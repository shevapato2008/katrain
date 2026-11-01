"""Short-lived, domain-separated acceptance of a server computed analysis price."""

import base64
import hashlib
import hmac
import json
from datetime import datetime

QUOTE_DOMAIN = b"katrain.membership.quote.v1\0"
FREE_ELIGIBILITY_POLICY = "trusted_identity_v1"


class QuoteError(ValueError):
    pass


def _b64(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def sign_quote(payload: dict, *, secret: str) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    signature = hmac.new(secret.encode(), QUOTE_DOMAIN + raw, hashlib.sha256).digest()
    return _b64(raw) + "." + _b64(signature)


def verify_quote(token: str, *, secret: str, now: datetime, user_id: int, environment: str) -> dict:
    try:
        if not isinstance(token, str) or len(token) > 8192:
            raise ValueError()
        data, signature = token.split(".")
        raw = _decode(data)
        expected = hmac.new(secret.encode(), QUOTE_DOMAIN + raw, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode(signature)):
            raise ValueError()
        payload = json.loads(raw)
        expires = datetime.fromisoformat(payload["expires_at"])
        if expires.tzinfo is None or now.tzinfo is None:
            raise ValueError()
        if payload["owner"] != user_id or payload["environment"] != environment or now >= expires:
            raise ValueError()
        if payload.get("source_policy") != "membership_then_wallet":
            raise ValueError()
        if type(payload.get("wallet_max_credits")) is not int or payload["wallet_max_credits"] < 0:
            raise ValueError()
        return payload
    except (ValueError, KeyError, TypeError, UnicodeError, OverflowError):
        raise QuoteError("invalid_or_expired_quote") from None


def canonical_analysis_input(sgf, kind, profile):
    # Keep the canonical input implementation independently testable without importing billing or its DB.
    from .billing_input import canonical_analysis_input as canonicalize

    return canonicalize(sgf, kind, profile)
