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

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from katrain.web.api.v1.endpoints.auth import get_current_user, require_writable_user
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


@router.get("/quota")
async def get_quota(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """余额、免费周额度、以及「这些钱大概够几份复盘」。

    **先跑一次本用户的结算再报数**：对账器是 60 秒周期跑的，直接读余额会让用户
    在复盘刚跑完的那段窗口里看到一个偏低的数（预扣还没退差），看起来像被多扣了。

    `estimates` 就叫估算：真实成本按**实际分析到的手数**结算，认输的短棋更便宜。
    前端不得把它显示成「你还能复盘 N 局」这种确定口径。
    """
    if _is_board():
        _need_online()

    from katrain.web.core import analysis_cost, quota
    from katrain.web.core.report_settlement import settle_finished_reports

    settle_finished_reports(db, user_id=current_user.id)
    used, allowance = quota.peek(
        db, current_user.id, "free_report:week", allowance=settings.FREE_WEEKLY_REPORTS
    )
    return {
        "credits": billing.get_balance(db, current_user.id),
        "free_weekly": {"used": used, "allowance": allowance},
        "estimates": {
            "normal_250_moves": analysis_cost.report_cost(250, 500),
            "deep_250_moves": analysis_cost.report_cost(250, 2000),
        },
        "billing_enforced": bool(settings.BILLING_ENFORCED),
        "billing_online": True,
    }


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
