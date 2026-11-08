"""Native payments: durable intent, network without DB transactions, atomic facts.

Only the verified client may supply transactions. Lock order is user then order.
A local timeout/cancel never proves provider closure. Each network stage commits
its claim first, and settlement is independent of current new-sale switches.
"""

from copy import deepcopy
from datetime import datetime, timedelta
import uuid
from time import monotonic

from sqlalchemy import or_

from . import membership as ms, models_db as m, payments
from .billing_catalog import CATALOG_VERSION

CHECK_SECONDS = 5
CREATE_LEASE_SECONDS = 60
SWEEP_BUDGET_SECONDS = 25
# Provider clamps time_expire to create+60s. Keep its 60s floor plus the
# client's 10s total budget / <=5s stalled read overshoot inside the frozen cutoff.
CREATE_MIN_REMAINING_SECONDS = 80


def _clock_from(now):
    """Advance the caller's wall clock across locks/HTTP using monotonic time."""
    started = monotonic()
    base = ms.utc(now)
    return lambda: base + timedelta(seconds=max(0, monotonic() - started))


def new_orders_enabled(settings):
    return settings.PAYMENTS_MODE == "live" and settings.MEMBERSHIP_MODE == "enabled"


def create_intent_in_transaction(db, *, user_id, sku, idempotency_key, now, settings, client=None):
    if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128:
        raise payments.PaymentError("invalid_idempotency_key", 422)
    user = payments._user(db, user_id)
    old = (
        db.query(m.RechargeOrder)
        .filter_by(user_id=user_id, idempotency_key=idempotency_key)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if old is None:
        # A restored intent may have been reached through a second browser key.
        # Bind that key permanently so retrying after settlement cannot buy again.
        candidates = (
            db.query(m.RechargeOrder)
            .filter_by(user_id=user_id, provider="wechat")
            .filter(m.RechargeOrder.payment_details.isnot(None))
            .all()
        )
        old = next(
            (row for row in candidates if idempotency_key in row.payment_details.get("idempotency_keys", [])), None
        )
    if old:
        if old.package_id != sku or old.provider != "wechat" or old.environment != settings.KATRAIN_ENVIRONMENT:
            raise payments.PaymentError("idempotency_conflict", 409)
        return old
    pending = (
        db.query(m.RechargeOrder)
        .filter_by(user_id=user_id, provider="wechat", status="pending")
        .filter(m.RechargeOrder.catalog_version.isnot(None), m.RechargeOrder.payment_details.isnot(None))
        .with_for_update()
        .populate_existing()
        .first()
    )
    if pending:
        if pending.environment != settings.KATRAIN_ENVIRONMENT:
            raise payments.PaymentError("payment_event_mismatch", 409)
        if pending.package_id != sku:
            raise payments.PaymentError("unresolved_payment_order", 409)
        details = dict(pending.payment_details)
        details["idempotency_keys"] = [*details.get("idempotency_keys", []), idempotency_key]
        pending.payment_details = details
        db.flush()
        return pending
    if not new_orders_enabled(settings) or client is None:
        raise payments.PaymentError("payments_unavailable", 503)
    frozen = payments._snapshot(sku, max_sale_enabled=settings.MEMBERSHIP_MAX_SALE_ENABLED)
    expiry = (ms.utc(now) + timedelta(minutes=15)).replace(microsecond=0)
    number = "wx" + uuid.uuid4().hex[:30]
    description = (
        f"智星盒 {frozen['plan_code'].title()} 30天会员"
        if frozen["kind"] == "membership"
        else f"智星盒 API充值 {frozen['amount_fen'] // 100}元"
    )
    request = {
        "appid": client.config.app_id,
        "mchid": client.config.mch_id,
        "description": description,
        "out_trade_no": number,
        "notify_url": client.config.notify_url,
        "time_expire": expiry.isoformat(),
        "amount": {"total": frozen["amount_fen"], "currency": "CNY"},
    }
    order = m.RechargeOrder(
        user_id=user.id,
        out_trade_no=number,
        package_id=sku,
        amount_fen=frozen["amount_fen"],
        credits=frozen["credits"],
        provider="wechat",
        status="pending",
        catalog_version=CATALOG_VERSION,
        sku_snapshot=frozen,
        environment=settings.KATRAIN_ENVIRONMENT,
        idempotency_key=idempotency_key,
        created_at=now,
        expires_at=expiry,
        payment_details={"request": request, "idempotency_keys": [idempotency_key]},
        payment_next_check_at=now,
    )
    db.add(order)
    db.flush()
    return order


def _locked(db, user_id, order_id):
    user = payments._user(db, user_id)
    order = payments._order(db, user_id, order_id)
    if order.provider != "wechat" or not isinstance(order.payment_details, dict):
        raise payments.PaymentError("order_not_found", 404)
    return user, order


def _binding(order, tx):
    request = order.payment_details["request"]
    if (
        tx.get("appid") != request["appid"]
        or tx.get("mchid") != request["mchid"]
        or tx.get("out_trade_no") != order.out_trade_no
    ):
        raise payments.PaymentError("payment_event_mismatch", 409)
    state = tx.get("trade_state")
    if state not in {"SUCCESS", "NOTPAY", "USERPAYING", "CLOSED", "REVOKED", "PAYERROR", "REFUND"}:
        raise payments.PaymentError("invalid_payment_status", 422)
    if tx.get("trade_type") is not None and tx["trade_type"] != "NATIVE":
        raise payments.PaymentError("payment_event_mismatch", 409)
    if state != "SUCCESS" and "amount" in tx:
        amount = tx["amount"]
        if (
            not isinstance(amount, dict)
            or ("total" in amount and (type(amount["total"]) is not int or amount["total"] != order.amount_fen))
            or ("currency" in amount and amount["currency"] != "CNY")
        ):
            raise payments.PaymentError("payment_event_mismatch", 409)
    if order.provider_tx_id and tx.get("transaction_id") and order.provider_tx_id != tx["transaction_id"]:
        raise payments.PaymentError("provider_transaction_conflict", 409)
    if state == "SUCCESS":
        amount = tx.get("amount")
        transaction_id = tx.get("transaction_id")
        if (
            tx.get("trade_type") != "NATIVE"
            or not isinstance(amount, dict)
            or type(amount.get("total")) is not int
            or amount["total"] != order.amount_fen
            or amount.get("currency") != "CNY"
        ):
            raise payments.PaymentError("payment_event_mismatch", 409)
        if not isinstance(transaction_id, str) or not 1 <= len(transaction_id) <= 128:
            raise payments.PaymentError("invalid_provider_transaction", 422)
        if order.provider_tx_id and order.provider_tx_id != transaction_id:
            raise payments.PaymentError("provider_transaction_conflict", 409)
        try:
            paid_at = datetime.fromisoformat(tx["success_time"].replace("Z", "+00:00"))
            if paid_at.tzinfo is None:
                raise ValueError()
        except (ValueError, KeyError, TypeError, AttributeError):
            raise payments.PaymentError("payment_time_mismatch", 409) from None
        return ms.utc(paid_at)
    return None


def _create_active(details, now):
    # A close racing an outstanding create is not final until a later verified
    # observation. Expired leases recover a crashed worker; no new create follows cancel.
    until = details.get("create_lease_until")
    return bool(details.get("create_token") and until and datetime.fromisoformat(until) > ms.utc(now))


def _closed(order, details, now):
    if _create_active(details, now):
        details["close_raced_create"] = True
    elif order.status == "pending":
        order.status = (
            "cancelled"
            if details.get("cancel_requested")
            else "expired" if ms.utc(now) >= ms.utc(order.expires_at) else "failed"
        )
    order.payment_details = details


def apply_transaction_in_transaction(db, *, transaction, now, settings):
    """Apply an authenticated/decrypted callback or signed query; no sale guard."""
    probe = (
        db.query(m.RechargeOrder.id, m.RechargeOrder.user_id)
        .filter_by(out_trade_no=transaction.get("out_trade_no"), provider="wechat")
        .one_or_none()
    )
    if probe is None:
        raise payments.PaymentError("order_not_found", 404)
    user, order = _locked(db, probe.user_id, probe.id)
    if order.environment != settings.KATRAIN_ENVIRONMENT:
        raise payments.PaymentError("payment_event_mismatch", 409)
    paid_at = _binding(order, transaction)
    if transaction["trade_state"] == "SUCCESS":
        if paid_at < ms.utc(order.created_at).replace(microsecond=0) or paid_at > ms.utc(now) + timedelta(minutes=5):
            raise payments.PaymentError("payment_time_mismatch", 409)
        duplicate = (
            db.query(m.RechargeOrder.id)
            .filter(
                m.RechargeOrder.environment == order.environment,
                m.RechargeOrder.provider == "wechat",
                m.RechargeOrder.provider_tx_id == transaction["transaction_id"],
                m.RechargeOrder.id != order.id,
            )
            .first()
        )
        if duplicate:
            raise payments.PaymentError("provider_transaction_conflict", 409)
        if order.status not in {"paid", "refunded"}:
            payments.fulfill_order_in_transaction(
                db, user=user, order=order, provider_tx_id=transaction["transaction_id"], paid_at=paid_at, now=now
            )
        order.payment_next_check_at = None
    elif order.status not in {"paid", "refunded"} and transaction["trade_state"] == "CLOSED":
        _closed(order, dict(order.payment_details), now)
    elif transaction["trade_state"] in {"REVOKED", "USERPAYING", "PAYERROR", "REFUND"}:
        # Native query docs explicitly restrict the first three to MICROPAY.
        # A refund observation cannot safely reverse already consumed assets;
        # refunds require the separately reviewed manual process in this release.
        details = dict(order.payment_details)
        details["observed_trade_state"] = transaction["trade_state"]
        details["provider_attention"] = (
            "refund_requires_review" if transaction["trade_state"] == "REFUND" else "unexpected_trade_state"
        )
        order.payment_details = details
    db.flush()
    return order


def _receipt(db, user_id, order_id, now, settings):
    order = db.query(m.RechargeOrder).filter_by(id=order_id, user_id=user_id).populate_existing().one_or_none()
    if order is None or not order.catalog_version:
        raise payments.PaymentError("order_not_found", 404)
    return payments.order_receipt(db, order, now=now, payments_mode=settings.PAYMENTS_MODE)


def _client(settings):
    from .wechat_native import WechatNativeClient, WechatNativeError

    try:
        return WechatNativeClient.from_settings(settings)
    except WechatNativeError:
        return None


def create_order(db, *, user_id, sku, idempotency_key, now, settings, client=None):
    clock = _clock_from(now)
    client = client or _client(settings)
    try:
        order = create_intent_in_transaction(
            db, user_id=user_id, sku=sku, idempotency_key=idempotency_key, now=clock(), settings=settings, client=client
        )
        oid = order.id
        db.commit()  # Durable intent exists before any provider request.
        if client:
            reconcile_order(db, user_id=user_id, order_id=oid, now=clock(), settings=settings, client=client)
        return _receipt(db, user_id, oid, clock(), settings)
    except Exception:
        db.rollback()
        raise


def cancel_order(db, *, user_id, order_id, now, settings, client=None):
    clock = _clock_from(now)
    try:
        _, order = _locked(db, user_id, order_id)
        if order.environment != settings.KATRAIN_ENVIRONMENT:
            raise payments.PaymentError("payment_event_mismatch", 409)
        if order.status == "pending":
            details = dict(order.payment_details)
            if not details.get("cancel_requested"):
                details["cancel_requested"] = True
                order.payment_details = details
                order.payment_next_check_at = clock()
        db.commit()
        reconcile_order(db, user_id=user_id, order_id=order_id, now=clock(), settings=settings, client=client)
        return _receipt(db, user_id, order_id, clock(), settings)
    except Exception:
        db.rollback()
        raise


def reconcile_order(db, *, user_id, order_id, now, settings, client=None):
    """Claim one due check, release transaction, fetch, then lock/apply facts."""
    from .wechat_native import WechatNativeError

    clock = _clock_from(now)
    client = client or _client(settings)
    try:
        _, order = _locked(db, user_id, order_id)
        now = clock()  # Locks may have waited across the payment cutoff.
        details = dict(order.payment_details)
        if order.environment != settings.KATRAIN_ENVIRONMENT:
            raise payments.PaymentError("payment_event_mismatch", 409)
        stop_requested = details.get("cancel_requested") or now >= ms.utc(order.expires_at)
        if order.status == "pending" and not details.get("create_attempted") and stop_requested:
            # No claim was committed, so no worker can have sent create. The
            # same locks prevent any future claim; no provider order can exist.
            _closed(order, details, now)
            db.commit()
            return _receipt(db, user_id, order_id, clock(), settings)
        if (
            client is None
            or order.status != "pending"
            or (order.payment_next_check_at and ms.utc(order.payment_next_check_at) > now)
        ):
            db.commit()
            return _receipt(db, user_id, order_id, clock(), settings)
        request = deepcopy(details["request"])
        order.payment_next_check_at = now + timedelta(seconds=CHECK_SECONDS)
        if client.config.mch_id != request["mchid"]:
            db.commit()
            return _receipt(db, user_id, order_id, clock(), settings)
        first_create = not details.get("create_attempted")
        allow_create = (
            new_orders_enabled(settings)
            and not details.get("cancel_requested")
            and (ms.utc(order.expires_at) - now).total_seconds() > CREATE_MIN_REMAINING_SECONDS
            and not _create_active(details, now)
        )
        token = None
        if first_create and allow_create:
            token = uuid.uuid4().hex
            details.update(
                create_attempted=True,
                create_token=token,
                create_lease_until=(now + timedelta(seconds=CREATE_LEASE_SECONDS)).isoformat(),
            )
            order.payment_details = details
        number = order.out_trade_no
        need_close = bool(stop_requested)
        db.commit()
        # No db read, lock or transaction between this commit and the HTTP call.
        if token:
            return _run_create(db, user_id, order_id, request, token, clock(), settings, client)
        try:
            tx = client.query(number)
        except WechatNativeError as exc:
            # 404 is never closure. Recheck wall time under fresh locks before
            # reusing frozen parameters; a slow query can cross the cutoff.
            if exc.status_code == 404 and allow_create and not details.get("code_url"):
                return _retry_create(db, user_id, order_id, clock(), settings, client)
            return _receipt(db, user_id, order_id, clock(), settings)
        now = clock()
        need_close = need_close or now >= datetime.fromisoformat(request["time_expire"])
        order = apply_transaction_in_transaction(db, transaction=tx, now=now, settings=settings)
        status = order.status
        db.commit()
        if status == "pending" and need_close and tx.get("trade_state") in {"NOTPAY", "CLOSED"}:
            try:
                client.close(number)  # Only a verified signed 204 returns.
            except WechatNativeError:
                return _receipt(db, user_id, order_id, clock(), settings)
            _, order = _locked(db, user_id, order_id)
            if order.status == "pending":
                _closed(order, dict(order.payment_details), clock())
            db.commit()
        return _receipt(db, user_id, order_id, clock(), settings)
    except Exception:
        db.rollback()
        raise


def _retry_create(db, user_id, order_id, now, settings, client):
    clock = _clock_from(now)
    _, order = _locked(db, user_id, order_id)
    now = clock()
    details = dict(order.payment_details)
    if (
        order.status != "pending"
        or details.get("cancel_requested")
        or (ms.utc(order.expires_at) - now).total_seconds() <= CREATE_MIN_REMAINING_SECONDS
        or not new_orders_enabled(settings)
        or _create_active(details, now)
    ):
        db.commit()
        return _receipt(db, user_id, order_id, clock(), settings)
    token = uuid.uuid4().hex
    details.update(
        create_attempted=True,
        create_token=token,
        create_lease_until=(now + timedelta(seconds=CREATE_LEASE_SECONDS)).isoformat(),
    )
    order.payment_details = details
    request = deepcopy(details["request"])
    db.commit()
    return _run_create(db, user_id, order_id, request, token, clock(), settings, client)


def _run_create(db, user_id, order_id, request, token, now, settings, client):
    from .wechat_native import WechatNativeError

    clock = _clock_from(now)
    code_url = None
    try:
        # Do not let provider's past-expiry clamping extend an expired intent.
        if (datetime.fromisoformat(request["time_expire"]) - clock()).total_seconds() > CREATE_MIN_REMAINING_SECONDS:
            code_url = client.create_native(request)
    except WechatNativeError:
        pass  # The provider may have accepted it; keep the same durable intent.
    _, order = _locked(db, user_id, order_id)
    details = dict(order.payment_details)
    if details.get("create_token") == token:
        details.pop("create_token", None)
        details.pop("create_lease_until", None)
        if code_url:
            details["code_url"] = code_url
        if details.get("cancel_requested") or details.get("close_raced_create"):
            order.payment_next_check_at = clock()
        order.payment_details = details
    db.commit()
    return _receipt(db, user_id, order_id, clock(), settings)


def reconcile_due_orders(session_factory, *, now, settings, limit=100, client=None):
    """Fair due scan, bounded elapsed budget and independently committed orders."""
    started = monotonic()
    clock = _clock_from(now)
    client = client or _client(settings)
    if client is None:
        return 0
    with session_factory() as db:
        rows = (
            db.query(m.RechargeOrder.id, m.RechargeOrder.user_id)
            .filter(
                m.RechargeOrder.provider == "wechat",
                m.RechargeOrder.status == "pending",
                m.RechargeOrder.catalog_version.isnot(None),
                m.RechargeOrder.payment_details.isnot(None),
                or_(m.RechargeOrder.payment_next_check_at.is_(None), m.RechargeOrder.payment_next_check_at <= clock()),
            )
            .order_by(m.RechargeOrder.payment_next_check_at.asc().nullsfirst(), m.RechargeOrder.id)
            .limit(limit)
            .all()
        )
    checked = 0
    for row in rows:
        if monotonic() - started >= SWEEP_BUDGET_SECONDS:
            break
        with session_factory() as db:
            try:
                reconcile_order(db, user_id=row.user_id, order_id=row.id, now=clock(), settings=settings, client=client)
                checked += 1
            except Exception:
                db.rollback()
                # Failure must not pin the first page forever. A fresh short tx
                # rotates even malformed orders while leaving settlement atomic.
                db.query(m.RechargeOrder).filter_by(id=row.id, provider="wechat", status="pending").update(
                    {"payment_next_check_at": clock() + timedelta(seconds=CHECK_SECONDS)}
                )
                db.commit()
    return checked
