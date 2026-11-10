"""Membership request counters. All mutations belong to the caller's transaction."""

from datetime import timedelta, timezone

from . import models_db as m
from .billing_catalog import CATALOG_VERSION, PLANS, TERM_DAYS, wallet_display_points

BILLING_TZ = timezone(timedelta(hours=8))
WEEK_KIND = "membership_week"
ACTIVE_OPERATION = ("reserved", "running")
ACTIVE_REPORT = ("authorizing", "pending", "running")


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def week_window(now):
    local = utc(now).astimezone(BILLING_TZ)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=local.weekday())
    year, week, _ = local.isocalendar()
    return f"W:{year}-W{week:02}", start.astimezone(timezone.utc), (start + timedelta(days=7)).astimezone(timezone.utc)


def current_term(db, *, user_id, now, lock=False):
    q = db.query(m.MembershipTerm).filter(
        m.MembershipTerm.user_id == user_id,
        m.MembershipTerm.status == "active",
        m.MembershipTerm.starts_at <= now,
        m.MembershipTerm.ends_at > now,
    )
    if lock:
        q = q.with_for_update()
    return q.populate_existing().order_by(m.MembershipTerm.starts_at, m.MembershipTerm.id).first()


def week_bucket(db, *, user_id, now, lock=False):
    key, _, _ = week_window(now)
    q = db.query(m.QuotaBucket).filter_by(user_id=user_id, kind=WEEK_KIND, period_key=key)
    return (q.with_for_update() if lock else q).populate_existing().one_or_none()


def legacy_free_facts(db, *, user_id, now):
    """Keep the old eligibility fact even when its game was deleted; only SGF proves units."""
    key, start, end = week_window(now)
    bucket = (
        db.query(m.QuotaBucket)
        .filter_by(user_id=user_id, kind="free_report", period_key=key)
        .populate_existing()
        .one_or_none()
    )
    used = int(bucket.used or 0) if bucket else 0
    tasks = (
        db.query(m.ReportTask)
        .filter(
            m.ReportTask.user_id == user_id, m.ReportTask.operation_id.is_(None), m.ReportTask.free_grant_period == key
        )
        .populate_existing()
        .all()
    )
    units = 0
    for task in tasks:
        if task.status not in (*ACTIVE_REPORT, "completed") or task.billing_exempt_reason:
            continue
        used = max(used, 1)
        game = db.query(m.UserGame).filter_by(id=task.user_game_id, user_id=user_id).populate_existing().one_or_none()
        if not game or not game.sgf_content:
            continue
        try:
            from .billing_quotes import canonical_analysis_input

            data = canonical_analysis_input(game.sgf_content, "report", "normal")
            units += data["move_count"] + 1
        except (ValueError, KeyError):
            pass
    return used > 0, units


def can_claim_free_report(db, *, user_id, now, trusted_free_eligible=False):
    if trusted_free_eligible is not True:
        return False, "verification_required"
    if current_term(db, user_id=user_id, now=now):
        return False, "paid_membership"
    key, start, end = week_window(now)
    if legacy_free_facts(db, user_id=user_id, now=now)[0]:
        return False, "weekly_report_used"
    used = (
        db.query(m.BillingOperation.id)
        .filter(
            m.BillingOperation.user_id == user_id,
            m.BillingOperation.kind == "report",
            m.BillingOperation.source.in_(("membership", "free_report")),
            m.BillingOperation.status.in_((*ACTIVE_OPERATION, "committed")),
            m.BillingOperation.created_at >= start,
            m.BillingOperation.created_at < end,
        )
        .first()
    )
    return (False, "weekly_report_used") if used else (True, None)


def ensure_week_bucket_in_transaction(db, *, user_id, now, allowance):
    row = week_bucket(db, user_id=user_id, now=now, lock=True)
    if row is None:
        key, start, end = week_window(now)
        row = m.QuotaBucket(
            user_id=user_id,
            kind=WEEK_KIND,
            period_key=key,
            allowance=allowance,
            used=legacy_free_facts(db, user_id=user_id, now=now)[1],
            reserved=0,
            starts_at=start,
            ends_at=end,
        )
        db.add(row)
        db.flush()
    elif row.allowance != allowance:
        row.allowance = allowance
    return row


def _order_entitlement(db, *, user_id, plan_id, order_id, for_new_term=False, term_catalog_version=None):
    """Use a server-frozen order; only unversioned legacy rows may use today's catalog."""
    order = db.query(m.RechargeOrder).filter_by(id=order_id, user_id=user_id).populate_existing().one_or_none()
    if order is None:
        raise ValueError("invalid_membership_order_snapshot")
    if order.catalog_version is not None:
        snapshot = order.sku_snapshot
        if (
            not order.catalog_version
            or not isinstance(snapshot, dict)
            or snapshot.get("kind") != "membership"
            or snapshot.get("plan_code") != plan_id
            or snapshot.get("sku") != f"membership_{plan_id}"
            or order.package_id != snapshot.get("sku")
            or type(snapshot.get("amount_fen")) is not int
            or snapshot["amount_fen"] <= 0
            or snapshot["amount_fen"] != order.amount_fen
            or type(snapshot.get("credits")) is not int
            or snapshot["credits"] != 0
            or order.credits != 0
            or any(
                type(snapshot.get(key)) is not int or snapshot[key] <= 0
                for key in ("term_days", "term_units", "week_units")
            )
            or snapshot["week_units"] > snapshot["term_units"]
            or (term_catalog_version is not None and term_catalog_version != order.catalog_version)
        ):
            raise ValueError("invalid_membership_order_snapshot")
        return {**snapshot, "catalog_version": order.catalog_version}
    # Legacy compatibility is deliberately bounded to this catalog. Missing frozen
    # facts on a versioned order never silently acquire current prices or benefits.
    if order.sku_snapshot is not None or term_catalog_version not in (None, CATALOG_VERSION) or plan_id not in PLANS:
        raise ValueError("invalid_membership_order_snapshot")
    if for_new_term and not PLANS[plan_id]["sellable"]:
        raise ValueError("plan_not_sellable")
    return {**PLANS[plan_id], "term_days": TERM_DAYS, "catalog_version": CATALOG_VERSION}


def term_week_units(db, term):
    return _order_entitlement(
        db,
        user_id=term.user_id,
        plan_id=term.plan_id,
        order_id=term.order_id,
        term_catalog_version=term.catalog_version,
    )["week_units"]


def create_term_in_transaction(db, *, user_id, plan_id, order_id, now):
    """The caller holds the user lock; same order replays its immutable term."""
    entitlement = _order_entitlement(db, user_id=user_id, plan_id=plan_id, order_id=order_id, for_new_term=True)
    existing = db.query(m.MembershipTerm).filter_by(order_id=order_id).populate_existing().one_or_none()
    if existing:
        if existing.user_id != user_id or existing.plan_id != plan_id:
            raise ValueError("order_term_conflict")
        return existing
    tail = (
        db.query(m.MembershipTerm)
        .filter_by(user_id=user_id, status="active")
        .populate_existing()
        .order_by(m.MembershipTerm.ends_at.desc())
        .first()
    )
    start = max(utc(now), utc(tail.ends_at)) if tail else utc(now)
    term = m.MembershipTerm(
        user_id=user_id,
        plan_id=plan_id,
        starts_at=start,
        ends_at=start + timedelta(days=entitlement["term_days"]),
        limit=entitlement["term_units"],
        used=0,
        reserved=0,
        order_id=order_id,
        catalog_version=entitlement["catalog_version"],
        status="active",
    )
    db.add(term)
    db.flush()
    return term


def _window(limit, used, reserved, reset):
    remaining = max(0, limit - used - reserved)
    return {
        "limit": limit,
        "used": used,
        "reserved": reserved,
        "remaining": remaining,
        "percent": round(remaining * 100 / limit, 2) if limit else 0,
        "reset_at": utc(reset).isoformat(),
    }


def usage_snapshot(
    db, *, user_id, now, environment, payments_mode, trusted_free_eligible=False, membership_mode="enabled"
):
    """Pure read: never opens a bucket, grants credits, commits, or reconciles."""
    user = db.query(m.User).filter_by(id=user_id).one()
    term = current_term(db, user_id=user_id, now=now)
    upcoming = (
        db.query(m.MembershipTerm)
        .filter(
            m.MembershipTerm.user_id == user_id, m.MembershipTerm.status == "active", m.MembershipTerm.starts_at > now
        )
        .order_by(m.MembershipTerm.starts_at)
        .first()
    )
    bucket = week_bucket(db, user_id=user_id, now=now)
    eligible, reason = can_claim_free_report(db, user_id=user_id, now=now, trusted_free_eligible=trusted_free_eligible)
    enabled = membership_mode == "enabled"

    def plan(t):
        return (
            {
                "code": t.plan_id,
                "name": {"plus": "Plus", "pro": "Pro", "max": "Max"}.get(t.plan_id, t.plan_id),
                "starts_at": utc(t.starts_at).isoformat(),
                "ends_at": utc(t.ends_at).isoformat(),
            }
            if t
            else None
        )

    _, _, week_end = week_window(now)
    week_used = int(bucket.used) if bucket else legacy_free_facts(db, user_id=user_id, now=now)[1]
    return {
        "catalog_version": CATALOG_VERSION,
        "server_now": utc(now).isoformat(),
        "revision": int(user.membership_revision or 0),
        "environment": environment,
        "capabilities": {
            "membership": enabled,
            "usage": membership_mode in ("enabled", "paused"),
            "quotes": enabled,
            "positions": enabled,
            "orders": enabled and payments_mode != "disabled",
            "can_claim_free_report": enabled and eligible,
            **({"reason": f"membership_{membership_mode}"} if not enabled else {}),
        },
        "payments_mode": payments_mode,
        "plan": {"current": plan(term), "next": plan(upcoming)},
        "term": _window(term.limit, term.used, term.reserved, term.ends_at) if term else None,
        "week": (
            _window(term_week_units(db, term), week_used, int(bucket.reserved or 0) if bucket else 0, week_end)
            if term
            else None
        ),
        "wallet": {"credits": int(user.credits or 0), "display_points": wallet_display_points(int(user.credits or 0))},
        "free": {
            "eligible": eligible,
            "remaining": 1 if eligible else 0,
            "limit": 1,
            "reset_at": week_end.isoformat(),
            "reason": reason,
        },
    }
