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

from katrain.web.api.v1.endpoints.auth import get_current_admin_user, get_current_user
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


@router.get("/quota")
async def get_quota(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """余额、免费周额度、以及「这些钱大概够几份复盘」。

    **先跑一次本用户的结算再报数**：对账器是 60 秒周期跑的，直接读余额会让用户
    在复盘刚跑完的那段窗口里看到一个偏低的数（预扣还没退差），看起来像被多扣了。

    `estimates` 就叫估算：真实成本按**实际分析到的手数**结算，认输的短棋更便宜。
    前端不得把它显示成「你还能复盘 N 局」这种确定口径。

    ⚠️ **`free_weekly` 只描述 `report_type="normal"` 那份额度**：免费分支写死了
    `task.report_type == "normal"`（reports.py），深度复盘对谁都不免费。而本响应里
    没有任何一格带 report_type 维度 —— 所以**前端不得把 `free_weekly` 显示在
    深度复盘按钮旁边**，那会让用户以为这次免费、实际照价扣费。
    """
    if _is_board():
        _need_online()

    from katrain.web.core import analysis_cost, quota
    from katrain.web.core.report_settlement import settle_finished_reports

    settle_finished_reports(db, user_id=current_user.id)
    # **未绑手机的用户绝不能触碰 quota。**
    # quota._ensure_bucket 只在**行不存在时**才 QuotaBucket(..., allowance=allowance),
    # 于是第一次触碰就把快照钉死在桶行上(peek 的 docstring 明写「限额取桶上的快照」)。
    # 拿 allowance=0 去 peek 一个未绑号用户 ⇒ 当周开出一个 allowance=0 的桶,
    # 该用户当周绑了手机也永远拿不到额度。所以在这里短路,一行桶都不建。
    #
    # 不只是「少建一行」:这两种写法编码的是**不同的事实**。
    # 「没有桶」= 没资格(权限事实);「allowance=0 的桶」= 有资格但额度为零(额度事实)。
    # 把前者写成后者,将来做「付费会员每周 3 次 / 免费用户 1 次 / 未绑手机 0 次」时
    # 就分不出后两者了 —— 而它们该有完全不同的引导文案。
    #
    # **`FREE_WEEKLY_REPORTS <= 0` 时同样不建桶**,理由与上面**逐字相同**,只是换了一根轴:
    # 额度关着时 peek 一次就把 allowance=0 钉在本周的桶行上,运维随后把它改成 1
    # (P3 落地开闸就是这个动作)时,当周看过 /quota 的人一律领不到 —— 要等下个 ISO 周。
    # 这条判据必须与 reports.py 免费分支的 `free_weekly_applies` **同形**:
    # 两个端点对「这次有没有免费额度」必须给同一个答案。
    #
    # ⚠️ **这条短路的正确性有两个前提,不是一个:**
    # (1) 不存在**自助**解绑 —— Task 9 的 bind_phone 对已绑号的账号返 "already_bound"
    #     而不是覆盖,本轮也不建解绑端点。⚠️ 但本轨道裁定的解绑方式是「人工客服直接改库」,
    #     那条路今天就通:客服把某个 used=1 的账号 phone_e164 置 NULL 之后,那行桶
    #     在 /quota 上会暂时不可见(到下个 ISO 周自愈)。只影响显示,不会多发额度;
    # (2) 库里没有属于未绑号用户的**存量**桶行 —— 有的话它的 used 会在 /quota 上
    #     整行消失(短路把 used 也一起写成 0),用户绑号后又突然冒出来,中间无解释。
    #     今天可证为空:桶只由这里的 peek(前端零调用方)与 reports 的 try_consume
    #     (要 BILLING_ENFORCED,默认 False)建。上线前的实测见轨道 plan.md 的部署清单。
    # 任一前提被打破,回来重看这里。
    if current_user.phone_bound and settings.FREE_WEEKLY_REPORTS > 0:
        used, allowance = quota.peek(
            db, current_user.id, "free_report:week", allowance=settings.FREE_WEEKLY_REPORTS
        )
        blocked_reason = None
    else:
        # 只有「额度本来发得出、就差这个手机」才叫 phone_required。
        # 额度整个关着时谁都是 0,对未绑号的人单独喊「去绑手机」是让他白跑一趟。
        #
        # **判据(下一个人会想改这里,先读这句)**:`blocked_reason` 解释的是
        # **它自己这个对象里的那几个数**,所以它为真当且仅当「绑上号会让这几个数变」。
        # 按这条尺子量三根轴:
        #   FREE_WEEKLY_REPORTS == 0 ⇒ 绑号后 peek 拿到的还是 0 ⇒ 数不变 ⇒ 不能说 phone_required(已挡);
        #   BILLING_ENFORCED == False ⇒ 绑号后 allowance 仍会 0→N(实测)⇒ 数**会**变
        #     ⇒ phone_required 是真话,**不要**把总闸并进这个条件。总闸开没开由同一份
        #     响应里的 `billing_enforced` 自己说,不归这个字段管;
        #   report_type 这根轴不在这里 —— /quota 不带 report_type,它只描述 normal
        #     复盘的那份额度(见本函数 docstring)。402 上的 `free_weekly_blocked` 才要管它。
        used, allowance = 0, 0
        blocked_reason = "phone_required" if settings.FREE_WEEKLY_REPORTS > 0 else None
    return {
        "credits": billing.get_balance(db, current_user.id),
        # blocked_reason 是必需的:没有它,前端分不出 allowance:0(没绑手机)
        # 与 used:1,allowance:1(本周已用完) —— 违反 spec §3.1 状态诚实。
        "free_weekly": {"used": used, "allowance": allowance, "blocked_reason": blocked_reason},
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
    current_user: User = Depends(get_current_user),
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
