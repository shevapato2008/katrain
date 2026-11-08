"""Authoritative billing endpoints with identity-bound cloud dispatch on kiosks.

Versioned membership routes never read the kiosk's cached wallet. Legacy wallet,
quota, prices and redeem routes keep their existing contracts.
"""

import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal

import httpx

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from katrain.web.api.v1.endpoints.auth import get_current_user, require_writable_user
from katrain.web.core import (
    billing,
    billing_catalog as catalog,
    billing_operations as operations,
    membership,
    models_db,
    payments,
    wechat_payments,
)
from katrain.web.core.billing_quotes import canonical_analysis_input
from katrain.web.core.repository import RemoteServiceUnavailableError
from katrain.web.core.ranked_session_guard import guard_user_has_no_pending_ranked_game
from katrain.web.core.config import settings
from katrain.web.core.db import get_db
from katrain.web.models import User


class NoStoreBillingRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def private_handler(request):
            try:
                response = await handler(request)
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}), "Cache-Control": "no-store"}
                raise
            except RequestValidationError as exc:
                return JSONResponse(
                    status_code=422,
                    content=jsonable_encoder({"detail": exc.errors()}),
                    headers={"Cache-Control": "no-store"},
                )
            response.headers["Cache-Control"] = "no-store"
            return response

        return private_handler


router = APIRouter(route_class=NoStoreBillingRoute)


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
    used, allowance = quota.peek(db, current_user.id, "free_report:week", allowance=settings.FREE_WEEKLY_REPORTS)
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


# Versioned membership journey. The wallet's existing credits retain their units.


async def get_trusted_free_eligibility() -> bool:
    """No production P3 proof provider exists yet. Unknown is ineligible.

    A test app may override this dependency only after validating its actual TEST DB.
    """
    return False


class BillingQuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["report", "position"]
    profile: Literal["normal", "advanced"]
    sgf: str | None = Field(default=None, max_length=262144)
    game_id: str | None = Field(default=None, max_length=64)
    session_id: str | None = Field(default=None, max_length=128)


class BillingOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: Literal["membership_plus", "membership_pro", "membership_max", "topup_10", "topup_30", "topup_100"]
    provider: Literal["mock", "live", "wechat"] | None = None
    idempotency_key: str = Field(min_length=1, max_length=128)


def _now():
    return datetime.now(timezone.utc)


def _private(response):
    response.headers["Cache-Control"] = "no-store"


def _membership_error(exc):
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.detail},
        headers={"Cache-Control": "no-store"},
    ) from exc


async def _cloud(request, method, user_id, *args):
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is None:
        _need_online()
    try:
        return await getattr(dispatcher, method)(*args, expected_user_id=user_id)
    except RemoteServiceUnavailableError:
        _need_online()
    except httpx.HTTPStatusError as exc:
        try:
            data = exc.response.json()
            detail = data.get("detail", data) if isinstance(data, dict) else data
        except ValueError:
            detail = "Cloud billing request failed"
        if exc.response.status_code >= 500:
            _need_online()
        raise HTTPException(
            status_code=exc.response.status_code, detail=detail, headers={"Cache-Control": "no-store"}
        ) from None


def resolve_analysis_input(db, *, user_id, body):
    """Exactly one input, resolved using its cloud owner; client counters are ignored."""
    if bool(body.sgf) == bool(body.game_id):
        raise HTTPException(
            422,
            detail={"code": "analysis_input_required", "message": "Supply sgf or game_id"},
            headers={"Cache-Control": "no-store"},
        )
    sgf = body.sgf
    if body.game_id:
        game = db.query(models_db.UserGame).filter_by(id=body.game_id, user_id=user_id).one_or_none()
        if game is None:
            raise HTTPException(
                404,
                detail={"code": "game_not_found", "message": "Game not found"},
                headers={"Cache-Control": "no-store"},
            )
        sgf = game.sgf_content
    try:
        return canonical_analysis_input(sgf, body.kind, body.profile)
    except ValueError as exc:
        raise HTTPException(
            422, detail={"code": "invalid_analysis_request", "message": str(exc)}, headers={"Cache-Control": "no-store"}
        ) from None


def _orders_available():
    if settings.PAYMENTS_MODE == "live":
        from katrain.web.core.wechat_native import wechat_native_ready

        return wechat_payments.new_orders_enabled(settings) and wechat_native_ready(settings)
    return (
        settings.MEMBERSHIP_MODE == "enabled"
        and settings.PAYMENTS_MODE == "mock"
        and settings.KATRAIN_ENVIRONMENT in {"test", "development"}
        and bool(settings.PAYMENT_MOCK_EVENT_SECRET)
    )


@router.get("/catalog")
async def get_catalog(request: Request, response: Response, current_user: User = Depends(get_current_user)):
    _private(response)
    if _is_board():
        return await _cloud(request, "billing_catalog", current_user.id)
    enabled = settings.MEMBERSHIP_MODE == "enabled"
    names = {"plus": "Plus", "pro": "Pro", "max": "Max"}
    return {
        "catalog_version": catalog.CATALOG_VERSION,
        "server_now": _now().isoformat(),
        "environment": settings.KATRAIN_ENVIRONMENT,
        "membership_mode": settings.MEMBERSHIP_MODE,
        "payments_mode": settings.PAYMENTS_MODE,
        "capabilities": {
            "membership": enabled,
            "usage": settings.MEMBERSHIP_MODE in {"enabled", "paused"},
            "quotes": enabled,
            "positions": enabled,
            "orders": _orders_available(),
            "can_claim_free_report": False,
            **({"reason": f"membership_{settings.MEMBERSHIP_MODE}"} if not enabled else {}),
        },
        "plans": [
            {
                "code": code,
                "name": names[code],
                "amount_fen": spec["amount_fen"],
                "term_days": catalog.TERM_DAYS,
                "term_units": spec["term_units"],
                "week_units": spec["week_units"],
                "term_report_reference": spec["term_units"] // 301,
                "week_report_reference": spec["week_units"] // 301,
                "full_use_savings_percent": round((1 - spec["amount_fen"] / spec["term_units"]) * 100, 1),
                "sale_enabled": enabled
                and catalog.is_plan_sellable(code, max_sale_enabled=settings.MEMBERSHIP_MAX_SALE_ENABLED),
            }
            for code, spec in catalog.PLANS.items()
        ],
        "topups": [
            {"sku": sku, **spec, "display_points": catalog.wallet_display_points(spec["credits"])}
            for sku, spec in catalog.TOPUPS.items()
        ],
        "profiles": {
            key: {
                "visits": spec["visits"],
                "credits_per_position": spec["units_per_position"],
                "display_points_per_position": catalog.wallet_display_points(spec["units_per_position"]),
            }
            for key, spec in catalog.PROFILES.items()
        },
    }


@router.get("/usage")
async def get_usage(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    trusted_free: bool = Depends(get_trusted_free_eligibility),
):
    _private(response)
    if _is_board():
        return await _cloud(request, "billing_usage", current_user.id)
    from katrain.web.core.report_settlement import settle_finished_reports

    settle_finished_reports(db, user_id=current_user.id)
    now = _now()
    operations.reconcile_expired_positions(db, now=now, user_id=current_user.id)
    db.commit()
    snapshot = membership.usage_snapshot(
        db,
        user_id=current_user.id,
        now=now,
        environment=settings.KATRAIN_ENVIRONMENT,
        payments_mode=settings.PAYMENTS_MODE,
        trusted_free_eligible=trusted_free,
        membership_mode=settings.MEMBERSHIP_MODE,
    )
    snapshot["capabilities"]["orders"] = _orders_available()
    return snapshot


@router.post("/quotes")
async def create_quote(
    body: BillingQuoteRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(require_writable_user),
    db: Session = Depends(get_db),
    trusted_free: bool = Depends(get_trusted_free_eligibility),
):
    _private(response)
    guard_user_has_no_pending_ranked_game(request.app, current_user, "analysis quote")
    if body.session_id:
        if body.kind != "position":
            raise HTTPException(422, detail={"code": "session_requires_position"})
        from katrain.web.api.v1.endpoints.paid_analysis import _position_input

        try:
            body = _position_input(request, body, current_user)
        except ValueError as exc:
            raise HTTPException(422, detail={"code": "invalid_analysis_request", "message": str(exc)}) from None
    if _is_board():
        return await _cloud(request, "billing_quote", current_user.id, body.model_dump(exclude_none=True))
    from katrain.web.core.report_settlement import settle_finished_reports

    settle_finished_reports(db, user_id=current_user.id)
    data = resolve_analysis_input(db, user_id=current_user.id, body=body)
    try:
        return operations.quote_operation(
            db,
            user_id=current_user.id,
            now=_now(),
            kind=body.kind,
            fingerprint=data["fingerprint"],
            profile=body.profile,
            units=(
                catalog.report_units(data["move_count"], body.profile)
                if body.kind == "report"
                else catalog.position_units(body.profile, move_count=data["move_count"])
            ),
            environment=settings.KATRAIN_ENVIRONMENT,
            secret=settings.SECRET_KEY,
            trusted_free_eligible=trusted_free,
            membership_mode=settings.MEMBERSHIP_MODE,
        )
    except operations.MembershipError as exc:
        _membership_error(exc)


@router.post("/orders")
async def create_billing_order(
    body: BillingOrderRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(require_writable_user),
    db: Session = Depends(get_db),
):
    _private(response)
    if _is_board():
        return await _cloud(request, "billing_create_order", current_user.id, body.model_dump(exclude_none=True))
    now = _now()
    try:
        if body.provider == "wechat" or (body.provider is None and settings.PAYMENTS_MODE == "live"):
            return await run_in_threadpool(
                wechat_payments.create_order,
                db,
                user_id=current_user.id,
                sku=body.sku,
                idempotency_key=body.idempotency_key,
                now=now,
                settings=settings,
            )
        order = payments.create_order_in_transaction(
            db,
            user_id=current_user.id,
            sku=body.sku,
            provider=body.provider,
            idempotency_key=body.idempotency_key,
            now=now,
            settings=settings,
        )
        db.commit()
        return payments.order_receipt(db, order, now=now, payments_mode=settings.PAYMENTS_MODE)
    except operations.MembershipError as exc:
        db.rollback()
        _membership_error(exc)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            detail={"code": "order_conflict", "message": "Order conflicts with an existing payment"},
            headers={"Cache-Control": "no-store"},
        ) from None


@router.get("/orders")
async def list_billing_orders(
    request: Request, response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _private(response)
    if _is_board():
        return await _cloud(request, "billing_list_orders", current_user.id)
    now = _now()
    try:
        payments.reconcile_pending_orders(db, now=now, settings=settings, user_id=current_user.id)
        db.commit()
        orders = (
            db.query(models_db.RechargeOrder)
            .filter(
                models_db.RechargeOrder.user_id == current_user.id, models_db.RechargeOrder.catalog_version.isnot(None)
            )
            .order_by(models_db.RechargeOrder.id.desc())
            .limit(100)
            .all()
        )
        return {
            "orders": [
                payments.order_receipt(db, order, now=now, payments_mode=settings.PAYMENTS_MODE) for order in orders
            ]
        }
    except operations.MembershipError as exc:
        db.rollback()
        _membership_error(exc)


@router.get("/orders/{order_id}")
async def get_billing_order(
    order_id: str,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _private(response)
    if _is_board():
        return await _cloud(request, "billing_get_order", current_user.id, order_id)
    try:
        try:
            oid = int(order_id)
        except ValueError:
            raise payments.PaymentError("order_not_found", 404) from None
        now = _now()
        probe = db.query(models_db.RechargeOrder).filter_by(id=oid, user_id=current_user.id).one_or_none()
        if probe and probe.provider == "wechat" and probe.catalog_version:
            return await run_in_threadpool(
                wechat_payments.reconcile_order, db, user_id=current_user.id, order_id=oid, now=now, settings=settings
            )
        order = payments.reconcile_order_in_transaction(
            db, user_id=current_user.id, order_id=oid, now=now, settings=settings
        )
        db.commit()
        return payments.order_receipt(db, order, now=now, payments_mode=settings.PAYMENTS_MODE)
    except operations.MembershipError as exc:
        db.rollback()
        _membership_error(exc)


@router.post("/orders/{order_id}/cancel")
async def cancel_billing_order(
    order_id: str,
    request: Request,
    response: Response,
    current_user: User = Depends(require_writable_user),
    db: Session = Depends(get_db),
):
    _private(response)
    if _is_board():
        return await _cloud(request, "billing_cancel_order", current_user.id, order_id)
    try:
        return await run_in_threadpool(
            wechat_payments.cancel_order, db, user_id=current_user.id, order_id=order_id, now=_now(), settings=settings
        )
    except operations.MembershipError as exc:
        db.rollback()
        _membership_error(exc)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail={"code": "order_conflict"}, headers={"Cache-Control": "no-store"}) from None
