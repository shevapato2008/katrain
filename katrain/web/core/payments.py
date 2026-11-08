"""Versioned checkout and atomic fulfillment; the caller owns every transaction.

Lock order is user -> order -> term/ledger. No provider network calls occur under locks.
Mock entry points retain TEST-only guards; Native orchestration lives in wechat_payments.
"""

from datetime import datetime, timedelta
import uuid

from . import billing, membership as ms, models_db as m
from .billing_catalog import CATALOG_VERSION, PLANS, TOPUPS, TERM_DAYS, is_plan_sellable, wallet_display_points
from .billing_environment import validate_runtime_environment
from .billing_operations import MembershipError


class PaymentError(MembershipError):
    pass


def require_mock_database(db, settings):
    try:
        verified = validate_runtime_environment(db.get_bind(), settings)
    except RuntimeError:
        raise PaymentError("mock_database_not_verified", 503) from None
    if not verified or settings.PAYMENTS_MODE != "mock":
        raise PaymentError("payments_unavailable", 503)
    if not settings.PAYMENT_MOCK_EVENT_SECRET:
        raise PaymentError("mock_secret_required", 503)


def _user(db, user_id):
    user = db.query(m.User).filter_by(id=user_id).with_for_update().populate_existing().one_or_none()
    if user is None:
        raise PaymentError("user_not_found", 404)
    return user


def _order(db, user_id, order_id):
    try:
        oid = int(order_id)
    except (ValueError, TypeError):
        raise PaymentError("order_not_found", 404) from None
    order = (
        db.query(m.RechargeOrder).filter_by(id=oid, user_id=user_id).with_for_update().populate_existing().one_or_none()
    )
    if order is None or not order.catalog_version or not order.sku_snapshot:
        raise PaymentError("order_not_found", 404)
    return order


def _snapshot(sku, *, max_sale_enabled):
    if sku in TOPUPS:
        return {"sku": sku, "kind": "topup", **TOPUPS[sku]}
    if isinstance(sku, str) and sku.startswith("membership_"):
        code = sku[len("membership_") :]
        if is_plan_sellable(code, max_sale_enabled=max_sale_enabled):
            return {
                "sku": sku,
                "kind": "membership",
                "plan_code": code,
                "amount_fen": PLANS[code]["amount_fen"],
                "credits": 0,
                "term_days": TERM_DAYS,
                "term_units": PLANS[code]["term_units"],
                "week_units": PLANS[code]["week_units"],
            }
    raise PaymentError("sku_not_sellable", 422)


def create_order_in_transaction(db, *, user_id, sku, provider, idempotency_key, now, settings):
    if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128:
        raise PaymentError("invalid_idempotency_key", 422)
    require_mock_database(db, settings)
    user = _user(db, user_id)
    old = (
        db.query(m.RechargeOrder)
        .filter_by(user_id=user_id, idempotency_key=idempotency_key)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    provider = provider or settings.PAYMENTS_MODE
    if old:
        if old.package_id != sku or old.provider != provider or old.environment != settings.KATRAIN_ENVIRONMENT:
            raise PaymentError("idempotency_conflict", 409)
        return old
    if settings.MEMBERSHIP_MODE != "enabled":
        raise PaymentError(f"membership_{settings.MEMBERSHIP_MODE}", 503)
    if provider != "mock":
        raise PaymentError("provider_unavailable", 503)
    frozen = _snapshot(sku, max_sale_enabled=settings.MEMBERSHIP_MAX_SALE_ENABLED)
    order = m.RechargeOrder(
        user_id=user.id,
        out_trade_no="membership_" + uuid.uuid4().hex,
        package_id=sku,
        amount_fen=frozen["amount_fen"],
        credits=frozen["credits"],
        provider=provider,
        status="pending",
        catalog_version=CATALOG_VERSION,
        sku_snapshot=frozen,
        environment=settings.KATRAIN_ENVIRONMENT,
        idempotency_key=idempotency_key,
        created_at=now,
        expires_at=ms.utc(now) + timedelta(minutes=15),
    )
    db.add(order)
    db.flush()
    return order


def validate_event_binding(order, event, settings):
    if (
        order.provider != "mock"
        or event.get("environment") != settings.KATRAIN_ENVIRONMENT
        or order.environment != event.get("environment")
        or order.user_id != event.get("owner_id")
        or type(event.get("amount_fen")) is not int
        or order.amount_fen != event["amount_fen"]
        or str(order.id) != str(event.get("order_id"))
    ):
        raise PaymentError("payment_event_mismatch", 409)
    tx = event.get("provider_tx_id")
    if not isinstance(tx, str) or not 1 <= len(tx) <= 128:
        raise PaymentError("invalid_provider_transaction", 422)
    if order.provider_tx_id and order.provider_tx_id != tx:
        raise PaymentError("provider_transaction_conflict", 409)
    if event.get("status") not in {"paid", "failed"}:
        raise PaymentError("invalid_payment_status", 422)


def apply_provider_event_in_transaction(db, *, event, now, settings):
    """Accept a previously authenticated provider fact, atomically granting once."""
    require_mock_database(db, settings)
    user = _user(db, event.get("owner_id"))
    order = _order(db, user.id, event.get("order_id"))
    validate_event_binding(order, event, settings)
    duplicate = (
        db.query(m.RechargeOrder.id)
        .filter(
            m.RechargeOrder.environment == order.environment,
            m.RechargeOrder.provider == order.provider,
            m.RechargeOrder.provider_tx_id == event["provider_tx_id"],
            m.RechargeOrder.id != order.id,
        )
        .first()
    )
    if duplicate:
        raise PaymentError("provider_transaction_conflict", 409)
    # Terminal successful facts cannot be downgraded by a delayed failure/replay.
    if order.status in {"paid", "refunded"}:
        return order
    if event["status"] == "failed":
        order.status = "failed"
        order.provider_tx_id = event["provider_tx_id"]
        db.flush()
        return order
    if order.status != "pending":
        raise PaymentError("order_not_payable", 409)
    paid_at = datetime.fromisoformat(event["_received_at"]) if "_received_at" in event else ms.utc(now)
    if paid_at < ms.utc(order.created_at) or paid_at > ms.utc(now):
        raise PaymentError("payment_time_mismatch", 409)
    if order.expires_at and paid_at >= ms.utc(order.expires_at):
        raise PaymentError("order_expired", 409)
    return fulfill_order_in_transaction(
        db, user=user, order=order, provider_tx_id=event["provider_tx_id"], paid_at=paid_at, now=now
    )


def fulfill_order_in_transaction(db, *, user, order, provider_tx_id, paid_at, now):
    """Shared grant primitive; callers authenticate facts and hold user/order locks."""
    snapshot = order.sku_snapshot
    if not isinstance(snapshot, dict) or snapshot.get("kind") not in {"membership", "topup"}:
        raise PaymentError("invalid_order_snapshot", 409)
    if snapshot["kind"] == "membership":
        # The owned, locked order is the entitlement authority. Current sale flags
        # only govern creation of a new order, never fulfillment of this snapshot.
        try:
            ms.create_term_in_transaction(
                db, user_id=user.id, plan_id=snapshot.get("plan_code"), order_id=order.id, now=now
            )
        except ValueError:
            raise PaymentError("invalid_order_snapshot", 409) from None
    elif snapshot["kind"] == "topup":
        billing.apply_adjustment(
            db, user.id, int(snapshot["credits"]), "membership_order", f"membership_order:{order.id}"
        )
        db.expire(user, ["credits"])
    else:
        raise PaymentError("invalid_order_snapshot", 409)
    order.status = "paid"
    order.provider_tx_id = provider_tx_id
    order.settled_at = paid_at
    order.fulfilled_at = now
    user.membership_revision += 1
    db.flush()
    return order


def refund_order_in_transaction(db, *, user_id, order_id, refund_ref, now, settings):
    require_mock_database(db, settings)
    if not isinstance(refund_ref, str) or not 1 <= len(refund_ref) <= 160:
        raise PaymentError("invalid_refund_key", 422)
    user = _user(db, user_id)
    order = _order(db, user_id, order_id)
    if order.environment != settings.KATRAIN_ENVIRONMENT or order.provider != "mock":
        raise PaymentError("payment_event_mismatch", 409)
    if order.status == "refunded":
        if order.refund_ref != refund_ref:
            raise PaymentError("refund_key_conflict", 409)
        return order
    if order.status != "paid":
        raise PaymentError("order_not_refundable", 409)
    if (
        db.query(m.RechargeOrder.id)
        .filter(m.RechargeOrder.refund_ref == refund_ref, m.RechargeOrder.id != order.id)
        .first()
    ):
        raise PaymentError("refund_key_conflict", 409)
    if order.sku_snapshot["kind"] == "topup":
        try:
            billing.apply_adjustment(
                db,
                user_id,
                -int(order.sku_snapshot["credits"]),
                "membership_order_refund",
                f"membership_refund:{order.id}",
            )
        except billing.InsufficientCredits:
            raise PaymentError("manual_refund_required", 409) from None
        db.expire(user, ["credits"])
    else:
        term = (
            db.query(m.MembershipTerm).filter_by(order_id=order.id).with_for_update().populate_existing().one_or_none()
        )
        later = (
            db.query(m.MembershipTerm.id)
            .filter(
                m.MembershipTerm.user_id == user_id,
                m.MembershipTerm.status == "active",
                m.MembershipTerm.id != term.id,
                m.MembershipTerm.starts_at >= term.ends_at,
            )
            .first()
            if term
            else None
        )
        if not term or term.used or term.reserved or later:
            raise PaymentError("manual_refund_required", 409)
        term.status = "refunded"
    order.status = "refunded"
    order.refund_ref = refund_ref
    order.refunded_at = now
    user.membership_revision += 1
    db.flush()
    return order


def order_receipt(db, order, *, now, payments_mode):
    snapshot = order.sku_snapshot
    fulfillment = None
    if order.fulfilled_at:
        if snapshot["kind"] == "topup":
            fulfillment = {"credits": snapshot["credits"], "display_points": wallet_display_points(snapshot["credits"])}
        else:
            term = db.query(m.MembershipTerm).filter_by(order_id=order.id).one_or_none()
            if term:
                fulfillment = {
                    "plan_code": term.plan_id,
                    "starts_at": ms.utc(term.starts_at).isoformat(),
                    "ends_at": ms.utc(term.ends_at).isoformat(),
                }
    receipt = {
        "id": str(order.id),
        "server_now": ms.utc(now).isoformat(),
        "sku": snapshot["sku"],
        "kind": snapshot["kind"],
        "status": (
            "expired"
            if order.provider != "wechat"
            and order.status == "pending"
            and order.expires_at
            and ms.utc(now) >= ms.utc(order.expires_at)
            else order.status
        ),
        "amount_fen": order.amount_fen,
        "currency": "CNY",
        "payments_mode": "live" if order.provider == "wechat" else payments_mode,
        "provider": order.provider,
        "created_at": ms.utc(order.created_at).isoformat(),
        "expires_at": ms.utc(order.expires_at).isoformat(),
        "paid_at": ms.utc(order.settled_at).isoformat() if order.settled_at else None,
        "fulfillment": fulfillment,
        "payment_url": None,
    }
    if order.provider == "wechat":
        details = order.payment_details or {}
        payable = (
            order.status == "pending"
            and not details.get("cancel_requested")
            and not details.get("provider_attention")
            and order.expires_at
            and ms.utc(now) < ms.utc(order.expires_at)
        )
        receipt["payment_url"] = details.get("code_url") if payable else None
        receipt["cancel_requested"] = bool(details.get("cancel_requested"))
        receipt["payment_state"] = (
            "paid"
            if order.status in {"paid", "refunded"}
            else (
                "closed"
                if order.status != "pending"
                else (
                    "ready"
                    if receipt["payment_url"]
                    else "creating" if payable and not details.get("create_attempted") else "confirming"
                )
            )
        )
    if receipt["status"] == "pending" and snapshot["kind"] == "membership":
        tail = (
            db.query(m.MembershipTerm)
            .filter_by(user_id=order.user_id, status="active")
            .order_by(m.MembershipTerm.ends_at.desc())
            .first()
        )
        start = max(ms.utc(now), ms.utc(tail.ends_at)) if tail else ms.utc(now)
        receipt.update(
            estimated_starts_at=start.isoformat(),
            estimated_ends_at=(start + timedelta(days=snapshot["term_days"])).isoformat(),
        )
    return receipt


def reconcile_order_in_transaction(db, *, user_id, order_id, now, settings):
    # Only durable TEST mock facts belong in this caller-owned transaction.
    # Native reconciliation owns separate short transactions around network calls.
    from .payment_mock import lookup_event

    probe = db.query(m.RechargeOrder).filter_by(id=order_id, user_id=user_id).one_or_none()
    if probe is None or not probe.catalog_version:
        raise PaymentError("order_not_found", 404)
    if probe.provider == "wechat":
        return probe
    fact = lookup_event(db, probe) if probe.provider == "mock" and settings.PAYMENTS_MODE == "mock" else None
    if fact and probe.status == "pending":
        return apply_provider_event_in_transaction(db, event=fact, now=now, settings=settings)
    if probe.status == "pending" and probe.expires_at and ms.utc(now) >= ms.utc(probe.expires_at):
        if probe.provider == "mock" and settings.PAYMENTS_MODE != "mock":
            return probe
        if probe.provider == "mock":
            require_mock_database(db, settings)
        _user(db, user_id)
        order = _order(db, user_id, order_id)
        if order.status == "pending":
            order.status = "expired"
            db.flush()
        return order
    return probe


def reconcile_pending_orders(db, *, now, settings, user_id=None, limit=100):
    """Maintenance/read recovery; caller commits once after this returns."""
    query = db.query(m.RechargeOrder).filter(
        m.RechargeOrder.catalog_version.isnot(None),
        m.RechargeOrder.status == "pending",
        m.RechargeOrder.provider != "wechat",
    )
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    rows = query.order_by(m.RechargeOrder.id).limit(limit).all()
    changed = 0
    for row in rows:
        before = row.status
        result = reconcile_order_in_transaction(db, user_id=row.user_id, order_id=row.id, now=now, settings=settings)
        changed += result.status != before
    return changed
