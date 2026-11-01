from datetime import datetime, timedelta, timezone
import pytest


def test_quotes_are_domain_separated_owner_environment_and_expiry_bound():
    from katrain.web.core.billing_quotes import sign_quote, verify_quote, QuoteError

    now = datetime(2026, 11, 2, tzinfo=timezone.utc)
    payload = {
        "owner": 1,
        "environment": "test",
        "kind": "position",
        "fingerprint": "a" * 64,
        "profile": "normal",
        "units": 1,
        "wallet_max_credits": 1,
        "catalog_version": "membership_20261102_v1",
        "source_policy": "membership_then_wallet",
        "expires_at": (now + timedelta(seconds=120)).isoformat(),
    }
    token = sign_quote(payload, secret="secret")
    assert verify_quote(token, secret="secret", now=now, user_id=1, environment="test") == payload
    for kwargs in ({"user_id": 2, "environment": "test"}, {"user_id": 1, "environment": "production"}):
        with pytest.raises(QuoteError):
            verify_quote(token, secret="secret", now=now, **kwargs)
    with pytest.raises(QuoteError):
        verify_quote(token, secret="secret", now=now + timedelta(seconds=121), user_id=1, environment="test")
    with pytest.raises(QuoteError):
        verify_quote(token + "tamper", secret="secret", now=now, user_id=1, environment="test")
