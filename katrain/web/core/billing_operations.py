"""Atomic membership/wallet authorizations and fenced settlement.

New admission: global transaction advisory lock -> user -> operation/task ->
term/week/credit. Settlement starts at user and never takes the global lock.
Nothing in this module commits, rolls back, or performs network I/O.
"""

import json
from datetime import timedelta
from sqlalchemy import text, or_

from . import billing, membership as ms, models_db as m
from .billing_catalog import CATALOG_VERSION, get_profile, wallet_display_points
from .billing_quotes import FREE_ELIGIBILITY_POLICY, sign_quote, verify_quote, QuoteError


class MembershipError(Exception):
    def __init__(self, code, status_code=409, detail=None):
        self.code, self.status_code, self.detail = code, status_code, detail or code
        super().__init__(self.detail)


def _enabled(mode):
    if mode != "enabled":
        raise MembershipError(f"membership_{mode}", 503)


def _validate(kind, fingerprint, profile, units):
    try:
        spec = get_profile(profile)
        if kind not in ("report", "position") or not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise ValueError()
        int(fingerprint, 16)
        step = spec["units_per_position"]
        if (
            type(units) is not int
            or (kind == "position" and units != step)
            or (kind == "report" and (units < 2 * step or units > 501 * step or units % step))
        ):
            raise ValueError()
        return spec
    except (TypeError, ValueError):
        raise MembershipError("invalid_analysis_request", 422) from None


def _user(db, user_id):
    user = db.query(m.User).filter_by(id=user_id).with_for_update().populate_existing().one_or_none()
    if user is None:
        raise MembershipError("user_not_found", 404)
    return user


def _source(db, *, user_id, now, kind, profile, units, trusted_free_eligible, lock=False):
    term = ms.current_term(db, user_id=user_id, now=now, lock=lock)
    bucket = ms.week_bucket(db, user_id=user_id, now=now, lock=lock)
    used = int(bucket.used) if bucket else ms.legacy_free_facts(db, user_id=user_id, now=now)[1]
    reserved = int(bucket.reserved or 0) if bucket else 0
    week_limit = ms.term_week_units(db, term) if term else 0
    if term and term.limit - term.used - term.reserved >= units and week_limit - used - reserved >= units:
        return "membership", term
    if (
        term is None
        and kind == "report"
        and profile == "normal"
        and ms.can_claim_free_report(db, user_id=user_id, now=now, trusted_free_eligible=trusted_free_eligible)[0]
    ):
        return "free_report", None
    return "wallet", term


def _owned(db, *, user_id, kind, fingerprint, profile, now):
    q = (
        db.query(m.BillingOperation)
        .filter_by(user_id=user_id, kind=kind, fingerprint=fingerprint, profile=profile, status="committed")
        .filter(m.BillingOperation.source != "owned")
        .populate_existing()
        .order_by(m.BillingOperation.id.desc())
    )
    if kind == "position":
        return q.filter(m.BillingOperation.result.isnot(None), m.BillingOperation.result_expires_at > now).first()
    # Reports live in their task/move tables. Their immutable receipt outlives
    # the short response-payload cache, but cannot promise a deleted result.
    spec = get_profile(profile)
    for op in q:
        task = (
            db.query(m.ReportTask)
            .filter_by(id=op.task_id, user_id=user_id, operation_id=op.id, status="completed")
            .populate_existing()
            .one_or_none()
            if op.task_id
            else None
        )
        if (
            task is None
            or task.generation != op.generation
            or task.model_sha256 != op.model_sha256
            or task.requested_visits != spec["visits"]
        ):
            continue
        game = db.query(m.UserGame.id).filter_by(id=task.user_game_id, user_id=user_id).first()
        if game and (not op.game_id or op.game_id == task.user_game_id):
            return op
    return None


def resolve_owned_operation(db, op):
    """Resolve a report's no-charge receipt to its still-owned original result.

    Position aliases contain the trusted bounded result and return themselves.
    Report aliases deliberately never replace the original task authorization.
    """
    if op.source != "owned" or op.kind != "report":
        return op
    task = (
        db.query(m.ReportTask)
        .filter_by(id=op.task_id, user_id=op.user_id, status="completed")
        .populate_existing()
        .one_or_none()
    )
    original = (
        db.query(m.BillingOperation).filter_by(id=task.operation_id).populate_existing().one_or_none() if task else None
    )
    if (
        original is None
        or original.source == "owned"
        or original.status != "committed"
        or original.task_id != task.id
        or original.game_id != op.game_id
        or (
            original.user_id,
            original.kind,
            original.fingerprint,
            original.profile,
            original.model_sha256,
            original.units,
            original.generation,
        )
        != (op.user_id, op.kind, op.fingerprint, op.profile, op.model_sha256, op.units, op.generation)
        or task.generation != original.generation
        or task.model_sha256 != original.model_sha256
        or task.requested_visits != get_profile(op.profile)["visits"]
        or not db.query(m.UserGame.id).filter_by(id=task.user_game_id, user_id=op.user_id).first()
    ):
        raise MembershipError("owned_result_unavailable", 409)
    return original


def _owned_receipt(db, *, original, idempotency_key, now):
    receipt = m.BillingOperation(
        user_id=original.user_id,
        kind=original.kind,
        idempotency_key=idempotency_key,
        fingerprint=original.fingerprint,
        source="owned",
        profile=original.profile,
        model_sha256=original.model_sha256,
        units=original.units,
        status="committed",
        generation=original.generation,
        task_id=original.task_id,
        game_id=original.game_id,
        result=json.loads(json.dumps(original.result)) if original.kind == "position" else None,
        result_expires_at=original.result_expires_at if original.kind == "position" else None,
        catalog_version=original.catalog_version,
        created_at=now,
        updated_at=now,
    )
    db.add(receipt)
    db.flush()
    return receipt


def quote_operation(
    db,
    *,
    user_id,
    now,
    kind,
    fingerprint,
    profile,
    units,
    environment,
    secret,
    trusted_free_eligible=False,
    membership_mode="enabled",
):
    _enabled(membership_mode)
    _validate(kind, fingerprint, profile, units)
    user = db.query(m.User).filter_by(id=user_id).one_or_none()
    if user is None:
        raise MembershipError("user_not_found", 404)
    owned = _owned(db, user_id=user_id, kind=kind, fingerprint=fingerprint, profile=profile, now=now)
    source, _ = _source(
        db,
        user_id=user_id,
        now=now,
        kind=kind,
        profile=profile,
        units=units,
        trusted_free_eligible=trusted_free_eligible,
    )
    if owned:
        source = "owned"
    if source == "wallet" and int(user.credits or 0) < units:
        if kind == "report" and not trusted_free_eligible and ms.current_term(db, user_id=user_id, now=now) is None:
            raise MembershipError("verification_required", 403)
        raise MembershipError("insufficient_credits", 402)
    expires = ms.utc(now) + timedelta(seconds=120)
    payload = {
        "owner": user_id,
        "environment": environment,
        "kind": kind,
        "fingerprint": fingerprint,
        "profile": profile,
        "units": units,
        "wallet_max_credits": 0 if source == "owned" else units,
        "catalog_version": CATALOG_VERSION,
        "source_policy": "membership_then_wallet",
        "source": source,
        "free_eligibility_policy": FREE_ELIGIBILITY_POLICY if source == "free_report" else None,
        "expires_at": expires.isoformat(),
    }
    return {
        "token": sign_quote(payload, secret=secret),
        **{k: v for k, v in payload.items() if k not in ("owner", "free_eligibility_policy")},
        "wallet_max_display_points": wallet_display_points(payload["wallet_max_credits"]),
        "server_now": ms.utc(now).isoformat(),
    }


def acquire_admission_lock(db):
    """Must precede the first user lock of any new-admission transaction."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(19467, 1102)"))


_admission_lock = acquire_admission_lock


def _check_slots(db, *, user_id, kind, report_queue_limit, position_queue_limit):
    active = db.query(m.BillingOperation).filter(
        m.BillingOperation.kind == kind, m.BillingOperation.status.in_(ms.ACTIVE_OPERATION)
    )
    if active.filter(m.BillingOperation.user_id == user_id).first():
        raise MembershipError("operation_in_progress", 409)
    if kind == "position":
        if active.count() >= position_queue_limit:
            raise MembershipError("queue_full", 429)
    else:
        tasks = db.query(m.ReportTask).filter(m.ReportTask.status.in_(ms.ACTIVE_REPORT))
        if tasks.filter(m.ReportTask.user_id == user_id).first():
            raise MembershipError("operation_in_progress", 409)
        # Count task-backed operations once, and authorizations that have not attached their task yet.
        unbound = active.filter(
            or_(
                m.BillingOperation.task_id.is_(None),
                ~m.BillingOperation.task_id.in_(
                    db.query(m.ReportTask.id).filter(m.ReportTask.status.in_(ms.ACTIVE_REPORT))
                ),
            )
        ).count()
        if tasks.count() + unbound >= report_queue_limit:
            raise MembershipError("queue_full", 429)


def reserve_operation_in_transaction(
    db,
    *,
    user_id,
    now,
    kind,
    fingerprint,
    profile,
    units,
    environment,
    secret,
    quote_token,
    idempotency_key,
    trusted_free_eligible=False,
    membership_mode="enabled",
    report_queue_limit=8,
    position_queue_limit=4,
    position_lease_seconds=90,
    game_id=None,
    task_id=None,
    wallet_max_credits=None,
):
    """Admit exactly once; accepted token is the sole wallet fallback cap authority."""
    _validate(kind, fingerprint, profile, units)
    if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128:
        raise MembershipError("invalid_idempotency_key", 422)
    _admission_lock(db)
    user = _user(db, user_id)
    old = (
        db.query(m.BillingOperation)
        .filter_by(user_id=user_id, kind=kind, idempotency_key=idempotency_key)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if old:
        if (old.fingerprint, old.profile, old.units) != (fingerprint, profile, units):
            raise MembershipError("idempotency_conflict", 409)
        if old.status == "committed" and old.result_expires_at and ms.utc(old.result_expires_at) <= ms.utc(now):
            raise MembershipError("result_expired", 410)
        return old
    _enabled(membership_mode)
    owned = _owned(db, user_id=user_id, kind=kind, fingerprint=fingerprint, profile=profile, now=now)
    if owned:
        return _owned_receipt(db, original=owned, idempotency_key=idempotency_key, now=now)
    try:
        accepted = verify_quote(quote_token, secret=secret, now=now, user_id=user_id, environment=environment)
    except QuoteError:
        raise MembershipError("invalid_or_expired_quote", 409) from None
    for key, value in {
        "kind": kind,
        "fingerprint": fingerprint,
        "profile": profile,
        "units": units,
        "catalog_version": CATALOG_VERSION,
    }.items():
        if accepted.get(key) != value:
            raise MembershipError("quote_mismatch", 409)
    if accepted.get("source") == "owned":
        raise MembershipError("owned_result_unavailable", 409)
    if accepted.get("source") == "free_report":
        if accepted.get("free_eligibility_policy") != FREE_ELIGIBILITY_POLICY:
            raise MembershipError("quote_mismatch", 409)
        # Revoked/unknown verification is an authorization change, not depleted
        # weekly capacity. It never authorizes a wallet fallback from a Free quote.
        if trusted_free_eligible is not True:
            raise MembershipError("verification_required", 403)
    # Legacy free grants remain authoritative until their old task reaches settlement.
    if (
        db.query(m.ReportTask.id)
        .filter(
            m.ReportTask.user_id == user_id,
            m.ReportTask.operation_id.is_(None),
            m.ReportTask.status.in_(ms.ACTIVE_REPORT),
        )
        .first()
    ):
        raise MembershipError("legacy_report_in_progress", 409)
    if (
        db.query(m.ReportTask.id)
        .join(m.CreditTransaction, m.ReportTask.charge_ref == m.CreditTransaction.ref_id)
        .filter(
            m.ReportTask.user_id == user_id,
            m.ReportTask.operation_id.is_(None),
            m.CreditTransaction.status == "reserved",
        )
        .first()
    ):
        raise MembershipError("legacy_report_in_progress", 409)
    reconcile_expired_positions(db, now=now, user_id=user_id)
    _check_slots(
        db, user_id=user_id, kind=kind, report_queue_limit=report_queue_limit, position_queue_limit=position_queue_limit
    )
    source, term = _source(
        db,
        user_id=user_id,
        now=now,
        kind=kind,
        profile=profile,
        units=units,
        trusted_free_eligible=trusted_free_eligible,
        lock=True,
    )
    if source == "wallet" and units > accepted["wallet_max_credits"]:
        raise MembershipError("wallet_cap_exceeded", 402)
    if source == "wallet" and int(user.credits or 0) < units:
        raise MembershipError("insufficient_credits", 402)
    spec = get_profile(profile)
    op = m.BillingOperation(
        user_id=user_id,
        kind=kind,
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
        source=source,
        profile=profile,
        model_sha256=spec["model_sha256"],
        units=units,
        status="reserved",
        generation=0,
        lease_expires_at=ms.utc(now) + timedelta(seconds=position_lease_seconds) if kind == "position" else None,
        task_id=task_id,
        game_id=game_id,
        catalog_version=CATALOG_VERSION,
        created_at=now,
        updated_at=now,
    )
    db.add(op)
    db.flush()
    if source in ("membership", "free_report"):
        if term:
            term = db.query(m.MembershipTerm).filter_by(id=term.id).with_for_update().populate_existing().one()
            op.term_id = term.id
            term.reserved += units
        bucket = ms.ensure_week_bucket_in_transaction(
            db, user_id=user_id, now=now, allowance=ms.term_week_units(db, term) if term else 0
        )
        bucket.reserved += units
        op.week_bucket_id = bucket.id
    else:
        op.wallet_ref = f"membership:operation:{op.id}"
        try:
            billing.reserve_in_transaction(
                db, user_id=user_id, amount=units, reason=f"membership_{kind}", ref_id=op.wallet_ref, now=now
            )
        except billing.InsufficientCredits:
            raise MembershipError("insufficient_credits", 402) from None
    user.membership_revision = int(user.membership_revision or 0) + 1
    user.membership_migrated_at = user.membership_migrated_at or now
    db.flush()
    return op


def _locked_operation(db, *, user_id, operation_id, generation):
    user = _user(db, user_id)
    op = (
        db.query(m.BillingOperation)
        .filter_by(id=operation_id, user_id=user_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if op is None:
        raise MembershipError("operation_not_found", 404)
    if generation is not None and op.generation != generation:
        raise MembershipError("stale_generation", 409)
    return user, op


def _release(db, op, *, commit, now):
    if op.term_id:
        term = db.query(m.MembershipTerm).filter_by(id=op.term_id).with_for_update().populate_existing().one()
        term.reserved -= op.units
        if commit:
            term.used += op.units
    if op.week_bucket_id:
        bucket = db.query(m.QuotaBucket).filter_by(id=op.week_bucket_id).with_for_update().populate_existing().one()
        bucket.reserved -= op.units
        if commit:
            bucket.used += op.units
    if op.wallet_ref:
        fn = billing.commit_in_transaction if commit else billing.refund_in_transaction
        fn(db, user_id=op.user_id, ref_id=op.wallet_ref, now=now)


def commit_operation_in_transaction(db, *, user_id, operation_id, now, generation=None, result=None):
    user, op = _locked_operation(db, user_id=user_id, operation_id=operation_id, generation=generation)
    if op.status == "committed":
        return op
    if op.status not in ms.ACTIVE_OPERATION:
        raise MembershipError("operation_closed", 409)
    if op.kind == "position" and op.lease_expires_at and ms.utc(op.lease_expires_at) <= ms.utc(now):
        raise MembershipError("lease_expired", 409)
    if result is not None and len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode()) > 65536:
        raise MembershipError("result_too_large", 422)
    _release(db, op, commit=True, now=now)
    op.status, op.updated_at, op.lease_expires_at = "committed", now, None
    op.result = result
    op.result_expires_at = ms.utc(now) + timedelta(hours=24) if op.kind == "position" else None
    user.membership_revision = int(user.membership_revision or 0) + 1
    db.flush()
    return op


def refund_operation_in_transaction(db, *, user_id, operation_id, now, generation=None):
    user, op = _locked_operation(db, user_id=user_id, operation_id=operation_id, generation=generation)
    if op.status not in ms.ACTIVE_OPERATION:
        return op
    _release(db, op, commit=False, now=now)
    op.status, op.updated_at, op.lease_expires_at, op.result = "refunded", now, None, None
    user.membership_revision = int(user.membership_revision or 0) + 1
    db.flush()
    return op


def reconcile_expired_positions(db, *, now, user_id=None, limit=200):
    candidates = db.query(m.BillingOperation.id, m.BillingOperation.user_id).filter(
        m.BillingOperation.kind == "position",
        m.BillingOperation.status.in_(ms.ACTIVE_OPERATION),
        m.BillingOperation.lease_expires_at <= now,
    )
    if user_id is not None:
        candidates = candidates.filter(m.BillingOperation.user_id == user_id)
    rows = candidates.order_by(m.BillingOperation.user_id, m.BillingOperation.id).limit(limit).all()
    count = 0
    for ident, owner in rows:
        user, op = _locked_operation(db, user_id=owner, operation_id=ident, generation=None)
        if (
            op.kind == "position"
            and op.status in ms.ACTIVE_OPERATION
            and op.lease_expires_at
            and ms.utc(op.lease_expires_at) <= ms.utc(now)
        ):
            op.generation += 1
            # Runtime sessions disable autoflush. Persist the fence within this
            # transaction before refund re-locks and refreshes the same receipt.
            db.flush([op])
            refund_operation_in_transaction(db, user_id=owner, operation_id=ident, now=now)
            count += 1
    # The receipt and idempotency identity survive bounded payload retention.
    expired = db.query(m.BillingOperation).filter(
        m.BillingOperation.result_expires_at <= now, m.BillingOperation.result.isnot(None)
    )
    if user_id is not None:
        expired = expired.filter(m.BillingOperation.user_id == user_id)
    for ident, owner in (
        expired.with_entities(m.BillingOperation.id, m.BillingOperation.user_id)
        .order_by(m.BillingOperation.user_id, m.BillingOperation.id)
        .limit(limit)
        .all()
    ):
        _, op = _locked_operation(db, user_id=owner, operation_id=ident, generation=None)
        if op.result_expires_at and ms.utc(op.result_expires_at) <= ms.utc(now):
            op.result = None
    db.flush()
    return count


usage_snapshot = ms.usage_snapshot
