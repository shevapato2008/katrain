"""Authenticated TEST-only provider facts, separate from customer payment intent."""

import hashlib
import hmac
import json

from . import models_db as m

DOMAIN = b"katrain.test-payment-event.v1\0"


def sign_event(event, *, secret):
    raw = json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hmac.new(secret.encode(), DOMAIN + raw, hashlib.sha256).hexdigest()


def verify_event(event, *, signature, secret):
    from .payments import PaymentError

    if (
        not secret
        or not isinstance(signature, str)
        or not hmac.compare_digest(sign_event(event, secret=secret), signature)
    ):
        raise PaymentError("invalid_mock_signature", 403)


def _key(order):
    return f"mock_payment:{order.environment}:{order.id}"


def lookup_event(db, order):
    row = db.get(m.SystemConfigDB, _key(order), populate_existing=True)
    return json.loads(row.value) if row else None


def record_event_in_transaction(db, *, event, signature, admin_user_id, now, settings, deliver=True):
    from .payments import (
        PaymentError,
        require_mock_database,
        _user,
        _order,
        validate_event_binding,
        apply_provider_event_in_transaction,
    )

    require_mock_database(db, settings)
    verify_event({**event, "deliver": deliver}, signature=signature, secret=settings.PAYMENT_MOCK_EVENT_SECRET)
    admin = db.query(m.User.id).filter_by(id=admin_user_id, is_admin=True).first()
    if not admin:
        raise PaymentError("test_admin_required", 403)
    _user(db, event.get("owner_id"))
    order = _order(db, event.get("owner_id"), event.get("order_id"))
    validate_event_binding(order, event, settings)
    prior = lookup_event(db, order)
    if prior and prior["provider_tx_id"] != event["provider_tx_id"]:
        raise PaymentError("provider_transaction_conflict", 409)
    # Bind even an undelivered provider fact to exactly one order (the unique DB index
    # also fences two admins recording the same provider transaction concurrently).
    order.provider_tx_id = event["provider_tx_id"]
    # Provider state also preserves paid against an out-of-order failure.
    fact = prior
    if not prior or prior["status"] != "paid":
        from .membership import utc

        if order.status == "pending" and event["status"] == "paid" and utc(now) >= utc(order.expires_at):
            raise PaymentError("order_expired", 409)
        row = db.get(m.SystemConfigDB, _key(order), populate_existing=True)
        if row is None:
            row = m.SystemConfigDB(key=_key(order), description="Isolated TEST payment provider fact")
            db.add(row)
        row.value = json.dumps({**event, "_received_at": utc(now).isoformat()}, sort_keys=True, separators=(",", ":"))
        db.flush()
        fact = json.loads(row.value)
    if deliver:
        return apply_provider_event_in_transaction(db, event=fact, now=now, settings=settings)
    return order
