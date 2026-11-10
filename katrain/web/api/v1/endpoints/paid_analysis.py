"""Owner-scoped, quoted short analysis. No network I/O occurs under a DB lock."""

import asyncio
from datetime import datetime, timezone
from typing import Literal
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from katrain.cron.clients.katago import KataGoClient
from katrain.web.api.v1.endpoints.auth import get_current_user, require_writable_user
from katrain.web.api.v1.endpoints.billing import NoStoreBillingRoute, _cloud, _membership_error, resolve_analysis_input
from katrain.web.core import billing_operations as ops, models_db as m
from katrain.web.core.billing_catalog import get_profile
from katrain.web.core.config import settings
from katrain.web.core.db import get_db
from katrain.web.core.paid_analysis import operation_receipt, paid_engine_client, session_position_sgf
from katrain.web.core.ranked_session_guard import guard_user_has_no_pending_ranked_game, temporary_analysis_lease
from katrain.web.models import User

router = APIRouter(route_class=NoStoreBillingRoute)


class CreatePositionAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Literal["normal", "advanced"]
    sgf: str | None = Field(default=None, max_length=262144)
    game_id: str | None = Field(default=None, max_length=64)
    session_id: str | None = Field(default=None, max_length=128)
    expected_position_key: str | None = Field(default=None, max_length=64)
    quote_token: str = Field(max_length=8192)
    idempotency_key: str = Field(min_length=1, max_length=128)


def now():
    return datetime.now(timezone.utc)


def _position_input(request, body, user):
    if body.session_id:
        try:
            session = request.app.state.session_manager.get_session(body.session_id)
        except KeyError:
            raise HTTPException(404, detail="Session not found") from None
        sgf = session_position_sgf(
            session, user, profile=body.profile, expected_position_key=body.expected_position_key
        )
        if body.game_id:
            raise HTTPException(422, detail="A local session cannot be a cloud game")
        if body.sgf:
            from katrain.web.core.billing_input import canonical_analysis_input

            if (
                canonical_analysis_input(sgf, "position", body.profile)["fingerprint"]
                != canonical_analysis_input(body.sgf, "position", body.profile)["fingerprint"]
            ):
                raise HTTPException(409, detail={"code": "position_changed", "message": "Session position changed"})
        return body.model_copy(update={"sgf": sgf, "session_id": None, "expected_position_key": None})
    return body


@router.post("/positions")
async def create_position(
    body: CreatePositionAnalysis,
    request: Request,
    response: Response,
    current_user: User = Depends(require_writable_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    guard_user_has_no_pending_ranked_game(request.app, current_user, "paid position analysis")
    try:
        body = _position_input(request, body, current_user)
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "invalid_analysis_request", "message": str(exc)}) from None
    if settings.KATRAIN_MODE == "board":
        return await _cloud(request, "paid_position", current_user.id, body.model_dump(exclude_none=True))
    data = resolve_analysis_input(
        db,
        user_id=current_user.id,
        body=SimpleNamespace(sgf=body.sgf, game_id=body.game_id, kind="position", profile=body.profile),
    )
    profile = get_profile(body.profile)
    try:
        op = ops.reserve_operation_in_transaction(
            db,
            user_id=current_user.id,
            now=now(),
            kind="position",
            fingerprint=data["fingerprint"],
            profile=body.profile,
            units=profile["units_per_position"],
            environment=settings.KATRAIN_ENVIRONMENT,
            secret=settings.SECRET_KEY,
            quote_token=body.quote_token,
            idempotency_key=body.idempotency_key,
            membership_mode=settings.MEMBERSHIP_MODE,
            position_queue_limit=settings.MEMBERSHIP_POSITION_QUEUE_LIMIT,
            report_queue_limit=settings.MEMBERSHIP_REPORT_QUEUE_LIMIT,
            position_lease_seconds=min(settings.MEMBERSHIP_POSITION_LEASE_SECONDS, 90),
            game_id=body.game_id,
        )
        execute = op.status == "reserved"
        if execute:
            op.status = "running"
        operation_id, generation = op.id, op.generation
        receipt = operation_receipt(db, op)
        db.commit()
    except ops.MembershipError as exc:
        db.rollback()
        _membership_error(exc)
    if not execute:
        return receipt
    # Snapshot all request identity before awaiting; no account switching can redirect settlement.
    user_id = current_user.id
    request_id = f"position:{operation_id}:{generation}"
    try:
        client = getattr(request.app.state, "paid_analysis_client", None) or paid_engine_client()
        with temporary_analysis_lease(
            request.app, current_user, f"position:{operation_id}", "paid-position", "paid analysis"
        ):
            raw = await asyncio.wait_for(
                client.analyze(
                    request_id=request_id,
                    moves=data["moves"],
                    rules=data["rules"],
                    komi=data["komi"],
                    board_size=data["board_size"],
                    max_visits=profile["visits"],
                    analyze_turns=[data["move_count"]],
                    include_ownership=True,
                    include_policy=False,
                    initial_stones=data["initial_stones"],
                    initial_player=data["initial_player"],
                    expected_model_sha256=profile["model_sha256"],
                ),
                timeout=80,
            )
            KataGoClient.validate_result(
                raw,
                request_id,
                data["move_count"],
                data["board_size"],
                profile["model_sha256"],
                min_visits=profile["visits"],
            )
            # Bounded, finite output; never persist the unrestricted upstream response.
            result = {
                "ownership": raw["ownership"],
                "moves": [
                    {
                        "move": move["move"],
                        "visits": move["visits"],
                        "winrate": move["winrate"],
                        "score_lead": move["scoreLead"],
                        "pv": move.get("pv", [])[:500],
                    }
                    for move in raw["moveInfos"][:30]
                ],
                "rootInfo": {key: raw["rootInfo"][key] for key in ("visits", "winrate", "scoreLead")},
            }
            guard_user_has_no_pending_ranked_game(request.app, current_user, "paid position result")
            op = ops.commit_operation_in_transaction(
                db, user_id=user_id, operation_id=operation_id, now=now(), generation=generation, result=result
            )
            receipt = operation_receipt(db, op)
            db.commit()
            return receipt
    except (Exception, asyncio.CancelledError) as exc:
        db.rollback()
        try:
            ops.refund_operation_in_transaction(
                db, user_id=user_id, operation_id=operation_id, now=now(), generation=generation
            )
            db.commit()
        except ops.MembershipError:
            db.rollback()
        if isinstance(exc, (asyncio.CancelledError, HTTPException)):
            raise
        op = db.query(m.BillingOperation).filter_by(id=operation_id, user_id=user_id, kind="position").one()
        return operation_receipt(db, op)


@router.get("/positions/{operation_id}")
async def get_position(
    operation_id: str,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    guard_user_has_no_pending_ranked_game(request.app, current_user, "paid position result")
    if settings.KATRAIN_MODE == "board":
        return await _cloud(request, "paid_position_get", current_user.id, operation_id)
    if not operation_id.isdecimal() or len(operation_id) > 18:
        raise HTTPException(404, detail={"code": "operation_not_found"})
    ops.reconcile_expired_positions(db, now=now(), user_id=current_user.id)
    db.commit()
    op = (
        db.query(m.BillingOperation)
        .filter_by(id=int(operation_id), user_id=current_user.id, kind="position")
        .one_or_none()
    )
    if op is None:
        raise HTTPException(404, detail={"code": "operation_not_found"})
    return operation_receipt(db, op)
