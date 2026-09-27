"""Users & billing for the admin console: read-only lookups, audited credit adjustments and redeem codes.

Every write commits together with its `admin_audit_log` row — if the audit row cannot be written,
the business write rolls back. Responses use explicit field lists; password hashes, tokens and
full redeem codes (after the one-time generation response) never leave this module.
"""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from katrain.web.admin.cron_health import as_utc
from katrain.web.admin.routers.tutorials import get_admin_db
from katrain.web.admin.session import get_current_admin
from katrain.web.core import billing
from katrain.web.core.models_db import AdminAuditLog, CreditTransaction, QuotaBucket, RedeemCode, User

router = APIRouter(dependencies=[Depends(get_current_admin)])

MAX_ADJUST = 12000  # the largest recharge package
MAX_CODES = 200
MAX_CODE_CREDITS = 12000
MAX_CODE_DAYS = 365
SHANGHAI = ZoneInfo("Asia/Shanghai")
KEY_PATTERN = r"^[0-9a-f]{32}$"


def _iso(value: datetime | None) -> str | None:
    return as_utc(value).isoformat() if value is not None else None


def _mask(code: str) -> str:
    return f"{code[:4]}…{code[-4:]}"


def _user_row(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "rank": user.rank,
        "credits": int(user.credits or 0),
        "is_admin": bool(user.is_admin),
        "created_at": _iso(user.created_at),
    }


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


def _audit(db: Session, admin: dict, action: str, target_type: str | None, target_id: int | None, detail: dict) -> None:
    db.add(
        AdminAuditLog(
            actor_realm="admin",
            actor_username=admin["username"],
            action=action,
            target_type=target_type,
            target_id=target_id,
            success=True,
            detail=json.dumps(detail, ensure_ascii=False, sort_keys=True),
        )
    )


# ---------- users ----------


@router.get("/users")
def list_users(
    q: str = Query("", max_length=64), page: int = Query(1, ge=1, le=10000), db: Session = Depends(get_admin_db)
):
    page_size = 20
    query = select(User)
    q = q.strip()
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses = [User.username.like(f"{escaped}%", escape="\\"), User.uuid == q]
        if q.isdigit():
            clauses.append(User.id == int(q))
        query = query.where(or_(*clauses))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(User.id).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_user_row(u) for u in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/users/{user_id}")
def user_detail(user_id: int, db: Session = Depends(get_admin_db)):
    user = _get_user(db, user_id)
    reserved = db.execute(
        select(func.coalesce(func.sum(-CreditTransaction.delta), 0), func.count()).where(
            CreditTransaction.user_id == user_id, CreditTransaction.status == "reserved"
        )
    ).one()
    adjusted = db.scalar(
        select(func.coalesce(func.sum(CreditTransaction.delta), 0)).where(
            CreditTransaction.user_id == user_id, CreditTransaction.reason == "admin_adjust"
        )
    )
    return {
        **_user_row(user),
        "uuid": user.uuid,
        "reserved": {"amount": int(reserved[0]), "count": int(reserved[1])},
        "admin_adjust_total": int(adjusted),
    }


@router.get("/users/{user_id}/ledger")
def user_ledger(
    user_id: int,
    before_id: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_admin_db),
):
    _get_user(db, user_id)
    query = select(CreditTransaction).where(CreditTransaction.user_id == user_id)
    if before_id is not None:
        query = query.where(CreditTransaction.id < before_id)
    rows = db.scalars(query.order_by(CreditTransaction.id.desc()).limit(limit + 1)).all()
    items = [
        {
            "id": row.id,
            "created_at": _iso(row.created_at),
            "reason": row.reason,
            "delta": row.delta,
            "status": row.status,
            "balance_after": row.balance_after,
            "ref_id": row.ref_id,
        }
        for row in rows[:limit]
    ]
    return {"items": items, "next_before_id": items[-1]["id"] if len(rows) > limit else None}


@router.get("/users/{user_id}/quota")
def user_quota(user_id: int, db: Session = Depends(get_admin_db)):
    _get_user(db, user_id)
    rows = db.scalars(
        select(QuotaBucket).where(QuotaBucket.user_id == user_id).order_by(QuotaBucket.id.desc()).limit(20)
    ).all()
    return {
        "items": [
            {"kind": r.kind, "period_key": r.period_key, "allowance": r.allowance, "used": r.used} for r in rows
        ]
    }


@router.get("/users/{user_id}/redeemed")
def user_redeemed(user_id: int, db: Session = Depends(get_admin_db)):
    _get_user(db, user_id)
    rows = db.scalars(
        select(RedeemCode).where(RedeemCode.used_by == user_id).order_by(RedeemCode.used_at.desc()).limit(100)
    ).all()
    return {"items": [{"code": _mask(r.code), "credits": r.credits, "used_at": _iso(r.used_at)} for r in rows]}


class AdjustRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: int = Field(ge=-MAX_ADJUST, le=MAX_ADJUST)
    reason: str = Field(max_length=200)
    idempotency_key: str = Field(pattern=KEY_PATTERN)
    confirm_username: str = Field(max_length=128)
    confirm_amount: int

    @field_validator("amount")
    @classmethod
    def nonzero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("amount must not be zero")
        return value

    @field_validator("reason")
    @classmethod
    def meaningful(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("reason needs at least 5 characters")
        return value


def _replay(db: Session, row: CreditTransaction, user_id: int, amount: int) -> dict:
    if row.user_id != user_id or row.delta != amount:
        raise HTTPException(status_code=409, detail="这个幂等键已用于另一笔调整")
    return {"balance": billing.get_balance(db, user_id), "transaction_id": row.id, "replayed": True}


@router.post("/users/{user_id}/credits")
def adjust_credits(
    user_id: int, body: AdjustRequest, admin: dict = Depends(get_current_admin), db: Session = Depends(get_admin_db)
):
    user = _get_user(db, user_id)
    ref_id = f"admin_adjust:{body.idempotency_key}"
    existing = db.scalar(select(CreditTransaction).where(CreditTransaction.ref_id == ref_id))
    if existing is not None:
        return _replay(db, existing, user_id, body.amount)
    if body.confirm_username != user.username or body.confirm_amount != body.amount:
        raise HTTPException(status_code=409, detail="复核输入与目标用户或金额不一致")
    before = int(user.credits or 0)
    try:
        after = billing.apply_adjustment(db, user_id, body.amount, "admin_adjust", ref_id)
        _audit(
            db,
            admin,
            "credit_adjust",
            "user",
            user_id,
            {
                "amount": body.amount,
                "reason": body.reason,
                "balance_before": before,
                "balance_after": after,
                "key": body.idempotency_key,
            },
        )
        db.commit()
    except billing.InsufficientCredits as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"余额 {before}，不足以扣除 {-body.amount}") from exc
    except IntegrityError:
        db.rollback()
        winner = db.scalar(select(CreditTransaction).where(CreditTransaction.ref_id == ref_id))
        if winner is None:
            raise
        return _replay(db, winner, user_id, body.amount)
    except Exception:
        db.rollback()
        raise
    row = db.scalar(select(CreditTransaction).where(CreditTransaction.ref_id == ref_id))
    return {"balance": after, "transaction_id": row.id, "replayed": False}


# ---------- redeem codes ----------


class CodesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=1, le=MAX_CODES)
    credits: int = Field(ge=1, le=MAX_CODE_CREDITS)
    days: int = Field(ge=1, le=MAX_CODE_DAYS)
    note: str = Field(max_length=200)
    idempotency_key: str = Field(pattern=KEY_PATTERN)

    @field_validator("note")
    @classmethod
    def meaningful(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("note needs at least 5 characters")
        return value


@router.post("/redeem-codes")
def generate_codes(body: CodesRequest, admin: dict = Depends(get_current_admin), db: Session = Depends(get_admin_db)):
    seen = db.scalar(
        select(AdminAuditLog.id).where(
            AdminAuditLog.action == "redeem_codes_generate",
            AdminAuditLog.detail.like(f'%"key": "{body.idempotency_key}"%'),
        )
    )
    if seen is not None:
        raise HTTPException(status_code=409, detail="这批兑换码已经生成过，码值只显示一次")
    expires_at = datetime.now(timezone.utc) + timedelta(days=body.days)
    try:
        codes = billing.add_redeem_codes(db, body.count, body.credits, expires_at)
        _audit(
            db,
            admin,
            "redeem_codes_generate",
            "redeem_batch",
            None,
            {
                "count": body.count,
                "credits": body.credits,
                "expires_at": _iso(expires_at),
                "note": body.note,
                "key": body.idempotency_key,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"codes": codes, "count": body.count, "credits": body.credits, "expires_at": _iso(expires_at)}


@router.get("/redeem-codes")
def list_codes(db: Session = Depends(get_admin_db)):
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(RedeemCode, User.username)
        .outerjoin(User, User.id == RedeemCode.used_by)
        .order_by(RedeemCode.created_at.desc(), RedeemCode.expires_at.desc())
        .limit(200)
    ).all()
    audits = db.execute(
        select(AdminAuditLog.detail, AdminAuditLog.actor_username, AdminAuditLog.created_at)
        .where(AdminAuditLog.action == "redeem_codes_generate")
        .order_by(AdminAuditLog.id.desc())
        .limit(100)
    ).all()
    notes = {}
    for detail, actor, created in audits:
        try:
            parsed = json.loads(detail or "{}")
        except ValueError:
            continue
        notes[parsed.get("expires_at")] = (parsed, actor, created)
    # A batch is identified by its expiry instant (microsecond-exact, shared by every code in the batch).
    grouped = db.execute(
        select(
            RedeemCode.expires_at,
            RedeemCode.credits,
            func.count(),
            func.count(RedeemCode.used_by),
            func.min(RedeemCode.created_at),
        )
        .group_by(RedeemCode.expires_at, RedeemCode.credits)
        .order_by(func.min(RedeemCode.created_at).desc())
        .limit(50)
    ).all()
    batches = []
    for expires, credits, count, used, created in grouped:
        parsed, actor, audited_at = notes.get(_iso(expires), ({}, None, None))
        batches.append(
            {
                "created_at": _iso(audited_at or created),
                "credits": credits,
                "count": count,
                "used": used,
                "expires_at": _iso(expires),
                "note": parsed.get("note"),
                "created_by": actor,
            }
        )
    codes = []
    for code, username in rows:
        expired = code.used_by is None and code.expires_at is not None and as_utc(code.expires_at) <= now
        codes.append(
            {
                "code": _mask(code.code),
                "credits": code.credits,
                "expires_at": _iso(code.expires_at),
                "state": "used" if code.used_by is not None else "expired" if expired else "unused",
                "used_by": username,
                "used_at": _iso(code.used_at),
            }
        )
    return {"batches": batches, "codes": codes}


# ---------- audit ----------


def _day(value: str | None, end: bool) -> datetime | None:
    if not value:
        return None
    try:
        day = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="日期格式应为 YYYY-MM-DD") from exc
    moment = datetime.combine(day + timedelta(days=1) if end else day, time.min, tzinfo=SHANGHAI)
    return moment.astimezone(timezone.utc)


@router.get("/audit")
def audit_log(
    action: str | None = Query(None, max_length=64),
    since: str | None = Query(None, max_length=10),
    until: str | None = Query(None, max_length=10),
    target_user_id: int | None = Query(None, ge=1),
    page: int = Query(1, ge=1, le=10000),
    db: Session = Depends(get_admin_db),
):
    page_size = 50
    query = select(AdminAuditLog)
    if action:
        query = query.where(AdminAuditLog.action == action)
    start, end = _day(since, False), _day(until, True)
    if start is not None:
        query = query.where(AdminAuditLog.created_at >= start)
    if end is not None:
        query = query.where(AdminAuditLog.created_at < end)
    if target_user_id is not None:
        query = query.where(AdminAuditLog.target_type == "user", AdminAuditLog.target_id == target_user_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    user_ids = {r.target_id for r in rows if r.target_type == "user" and r.target_id is not None}
    names = dict(db.execute(select(User.id, User.username).where(User.id.in_(user_ids))).all()) if user_ids else {}
    items = []
    for row in rows:
        try:
            detail = json.loads(row.detail) if row.detail else None
        except ValueError:
            detail = row.detail
        items.append(
            {
                "id": row.id,
                "created_at": _iso(row.created_at),
                "actor_username": row.actor_username,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "target_label": names.get(row.target_id) if row.target_type == "user" else None,
                "success": row.success,
                "detail": detail,
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}
