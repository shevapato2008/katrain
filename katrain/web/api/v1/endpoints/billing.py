"""Billing / credits REST API (mounted at /api/v1/billing).

Server (cloud) mode is authoritative: these endpoints read/write the cloud DB.

Board (kiosk) mode is intentionally NOT served locally for balance-changing
operations — the kiosk must never spend against its cache-only SQLite (the
balance lives in the cloud). Until the cloud proxy is wired and live-tested,
board mode returns 503 need_online for spend/redeem/recharge so no local,
non-authoritative spend can ever happen. Read-only balance falls through to a
remote fetch if available, else need_online.
"""

import time
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from katrain.web.api.v1.endpoints.auth import get_current_admin_user, get_current_user, require_writable_user
from katrain.web.core import billing
from katrain.web.core.config import settings
from katrain.web.core.db import get_db
from katrain.web.models import User

router = APIRouter()


def _is_board() -> bool:
    return settings.KATRAIN_MODE == "board"


def _need_online():
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "need_online_billing", "message": "Billing requires a connection to the server"},
    )


# --- request/response models --------------------------------------------------


class RedeemRequest(BaseModel):
    code: str


class AdminGrantRequest(BaseModel):
    username: str
    amount: int


class AdminCodesRequest(BaseModel):
    count: int = 1
    credits: int


# --- naive per-user redeem rate limiter (best-effort, in-process) -------------

_redeem_attempts: dict = defaultdict(list)


def _check_redeem_rate(user_id: int):
    now = time.time()
    window = [t for t in _redeem_attempts[user_id] if now - t < 60]
    _redeem_attempts[user_id] = window
    if len(window) >= settings.REDEEM_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "message": "Too many attempts, try again later"},
        )


def _record_redeem_failure(user_id: int):
    _redeem_attempts[user_id].append(time.time())


# --- endpoints ----------------------------------------------------------------


@router.get("/balance")
async def get_balance(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if _is_board():
        # No authoritative local balance on kiosk; cloud proxy not yet wired.
        _need_online()
    return {"credits": billing.get_balance(db, current_user.id), "billing_online": True}


@router.get("/prices")
async def get_prices(current_user: User = Depends(get_current_user)):
    return {"prices": settings.BILLING_PRICES, "packages": settings.BILLING_PACKAGES}


@router.post("/redeem")
async def redeem(
    body: RedeemRequest,
    current_user: User = Depends(require_writable_user),
    db: Session = Depends(get_db),
):
    if _is_board():
        _need_online()
    _check_redeem_rate(current_user.id)
    try:
        new_balance = billing.redeem(db, current_user.id, body.code.strip())
    except billing.InvalidRedeemCode:
        _record_redeem_failure(current_user.id)
        # Intentionally indistinguishable error (don't leak code validity).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_code", "message": "Invalid or unusable code"},
        )
    return {"credits": new_balance}


@router.post("/admin/grant")
async def admin_grant(
    body: AdminGrantRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    if _is_board():
        _need_online()
    from katrain.web.core import models_db

    target = db.query(models_db.User).filter(models_db.User.username == body.username).one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="user not found")
    # ref_id makes repeated identical admin clicks idempotent within a second window.
    ref_id = f"admin_grant:{admin.id}:{target.id}:{body.amount}:{int(time.time())}"
    new_balance = billing.grant(db, target.id, body.amount, reason="admin_grant", ref_id=ref_id)
    return {"username": body.username, "credits": new_balance}


@router.post("/admin/codes")
async def admin_codes(
    body: AdminCodesRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    if _is_board():
        _need_online()
    codes = billing.generate_redeem_codes(db, count=body.count, credits=body.credits)
    return {"codes": codes, "credits_each": body.credits}
