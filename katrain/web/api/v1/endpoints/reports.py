from typing import Any
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session, object_session

from katrain.web.api.v1.endpoints.auth import get_current_user, require_writable_user
from katrain.web.api.v1.endpoints.billing import get_trusted_free_eligibility
from katrain.core import move_grade
from katrain.web.core import analysis_cost, billing, models_db, quota
from katrain.web.core import billing_operations
from katrain.web.core.billing_catalog import CATALOG_VERSION, report_units, wallet_display_points
from katrain.web.core.billing_quotes import canonical_analysis_input
from katrain.web.core.report_settlement import (
    is_membership_report,
    membership_report_readable,
    reconcile_membership_report_in_transaction,
)
from katrain.web.core.config import settings
from katrain.web.core.db import SessionLocal
from katrain.web.core.repository import RemoteServiceUnavailableError
from katrain.web.core.ranked_session_guard import guard_user_has_no_pending_ranked_game
from katrain.web.models import User

router = APIRouter()


def count_moves(sgf_content: str) -> int:
    """从 SGF 数出实际手数。

    **不要**信任 `UserGame.move_count`：那是 `UserGameCreate` 里客户端提交的字段
    （`user_games.py:32` 默认 0），拿它计价等于让付款方自己填金额。

    解析失败抛 ValueError —— 返回 0 会把「读不懂这份棋谱」伪装成「这份复盘不要钱」。
    """
    from katrain.core.sgf_parser import SGF, ParseError

    if not sgf_content or not sgf_content.strip():
        raise ValueError("空 SGF")
    try:
        root = SGF.parse_sgf(sgf_content)
    except ParseError as exc:
        # 只吞「这份棋谱解析不了」。**不要**写成 except Exception ——
        # 那会把 count_moves 自己的编程错误也包成 ValueError，
        # 端点返 400 unparsable_sgf，等于把我们的 bug 伪装成「你的棋谱有问题」，
        # 用户照着改棋谱永远改不好，日志里也看不见真正的堆栈。
        raise ValueError(f"SGF 解析失败: {exc}") from exc
    # 根节点自己也可能带一手：老式 SGF（如 tests/data/xmgt97.sgf）会把
    # 第一手和 SZ/KM 等对局信息塞在同一个根节点里。漏掉它会比 cron 的
    # parse_game 少数一手，于是 `moves[:paid_moves]` 会把最后一手真棋切掉。
    node = root
    n = 1 if node.move is not None else 0
    while node.children:
        node = node.children[0]
        if node.move is not None:
            n += 1
    return n


def sgf_fingerprint(sgf_content: str) -> str:
    """棋谱内容指纹。授权时冻结在任务上，cron 认领时比对（见 report_analyze.py）。

    `PUT /user-games/{id}` 可以在任务排队期间改 `sgf_content`；
    `moves[:paid_moves]` 只限得住手数，限不住内容 —— 没有这道指纹，配合
    `_get_resume_move_number` 的断点续跑，报告会拼成「旧棋谱前缀 + 新棋谱
    后缀」，且用户付的是旧棋谱的钱。
    """
    import hashlib

    return hashlib.sha256(sgf_content.encode("utf-8")).hexdigest()


REPORT_VISITS = {
    "normal": 500,
    "deep": 2000,
}


class ReportTaskCreate(BaseModel):
    user_game_id: str
    report_type: str = "normal"
    force: bool = False
    quote_token: str | None = None
    idempotency_key: str | None = None


class ReportTaskRetry(BaseModel):
    quote_token: str | None = None
    idempotency_key: str | None = None


class ReportTaskStatus(BaseModel):
    id: int
    user_game_id: str
    status: str
    report_type: str
    total_moves: int
    analyzed_moves: int
    requested_visits: int
    operation_id: int | None = None
    authorization_operation_id: int | None = None
    operation_status: str | None = None
    billing_version: str | None = None
    source: str | None = None
    wallet_credits: int = 0
    wallet_display_points: str = "0.00"
    # ISO 8601, or null when the attempt has not started / not finished.
    #
    # `started_at` is when the *current* attempt series began, not when the row was
    # created: the cron worker stamps it on claim with `started_at or now()`, so the
    # automatic retries inside one series keep the first stamp, and `/retry` clears it
    # so the next claim re-stamps. `completed_at` is set only on success and is cleared
    # by every path that puts the task back in the queue -- so the pair is either a
    # finished span or nothing, never a half-open one left over from an earlier run.
    #
    # Consumers show a duration as `completed_at - started_at`. Both come from the same
    # column type, so on SQLite (dev) both are naive and on PostgreSQL (prod) both carry
    # an offset -- the difference is right either way, only an absolute instant would
    # need the caller to know which.
    started_at: str | None = None
    completed_at: str | None = None


class ReportTaskMoveResponse(BaseModel):
    id: int
    task_id: int
    move_number: int
    status: str | None = None
    winrate: float | None = None
    score_lead: float | None = None
    visits: int | None = None
    top_moves: Any | None = None
    ownership: Any | None = None
    actual_move: str | None = None
    actual_player: str | None = None
    delta_score: float | None = None
    delta_winrate: float | None = None
    # 着手评价（服务端算好，前端只查表）。grade 为 None 或 "unrated" 表示
    # 这手没有被评级 —— 前端要显示成「未评级」，不能当作「没问题」。
    grade: str | None = None
    points_lost: float | None = None
    points_lost_source: str | None = None
    is_top_move: bool | None = None
    top_prior: float | None = None
    brilliance: int | None = None
    root_visits: int | None = None


def get_report_db(request: Request):
    session_factory = getattr(request.app.state, "report_session_factory", SessionLocal)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def _task_to_dict(task: models_db.ReportTask, receipt=None) -> dict[str, Any]:
    db = object_session(task)
    op = receipt or (db.get(models_db.BillingOperation, task.operation_id) if db and task.operation_id else None)
    wallet_credits = op.units if op and op.source == "wallet" and op.status != "refunded" else 0
    return {
        "id": task.id,
        "user_game_id": task.user_game_id,
        "status": task.status,
        "report_type": task.report_type,
        "total_moves": task.total_moves,
        "analyzed_moves": task.analyzed_moves,
        "requested_visits": task.requested_visits,
        "operation_id": op.id if op else task.operation_id,
        "authorization_operation_id": task.operation_id,
        "operation_status": op.status if op else None,
        "billing_version": task.billing_version,
        "source": op.source if op else None,
        "wallet_credits": wallet_credits,
        "wallet_display_points": wallet_display_points(wallet_credits),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def _move_to_dict(move: models_db.ReportTaskMove) -> dict[str, Any]:
    return {
        "id": move.id,
        "task_id": move.task_id,
        "move_number": move.move_number,
        "status": move.status,
        "winrate": move.winrate,
        "score_lead": move.score_lead,
        "visits": move.visits,
        "top_moves": move.top_moves,
        "ownership": move.ownership,
        "actual_move": move.actual_move,
        "actual_player": move.actual_player,
        "delta_score": move.delta_score,
        "delta_winrate": move.delta_winrate,
        "grade": move.grade,
        "points_lost": move.points_lost,
        "points_lost_source": move.points_lost_source,
        "is_top_move": move.is_top_move,
        "top_prior": move.top_prior,
        "brilliance": move.brilliance,
        "root_visits": move.root_visits,
    }


def _moves_with_grades(moves: list[models_db.ReportTaskMove]) -> list[dict[str, Any]]:
    """序列化，并给还没有评级的行**按需补算**。

    改成服务端评级之前生成的报告，grade 列是 NULL。那些行里 top_moves / actual_move
    都还在，所以不用重新分析棋局就能补出评级 —— 在这里补，而不是让前端自己再实现
    一份判据（仓里为此已经散了五份阈值，这条路不能再走）。

    补算是只读的，不写回库；重新生成报告时 cron 会把它们持久化。
    """
    out: list[dict[str, Any]] = []
    prev: models_db.ReportTaskMove | None = None
    for move in moves:
        data = _move_to_dict(move)
        if not data.get("grade") and prev is not None:
            g = move_grade.grade_move(
                prev_top_moves=prev.top_moves,
                prev_visits=prev.root_visits,
                actual_move=move.actual_move,
                actual_player=move.actual_player,
                actual_score_lead=move.score_lead,
                actual_winrate=move.winrate,
                move_number=move.move_number,
            )
            data.update(
                grade=g["grade"],
                points_lost=g["points_lost"],
                points_lost_source=g["points_lost_source"],
                is_top_move=g["is_top_move"],
                top_prior=g["top_prior"],
                brilliance=g["brilliance"],
            )
        out.append(data)
        prev = move
    return out


def _upstream_error_detail(response: httpx.Response):
    try:
        payload = response.json()
    except ValueError:
        return response.text
    if isinstance(payload, dict) and "detail" in payload:
        return payload["detail"]
    return payload


async def _dispatch_remote_only(call):
    try:
        return await call()
    except RemoteServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=_upstream_error_detail(exc.response),
        ) from exc


def _membership_http_error(exc):
    return HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.detail})


def _reconcile_paid_report(db, *, task_id, user_id):
    try:
        task, op = reconcile_membership_report_in_transaction(db, task_id=task_id, user_id=user_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Report task not found")
        return task, op
    except billing_operations.MembershipError as exc:
        raise _membership_http_error(exc) from exc


def _membership_user(db, user_id, *, app=None):
    from katrain.web.core.paid_analysis import legacy_analysis_allowed

    user = db.get(models_db.User, user_id)
    return not legacy_analysis_allowed(user=user, app=app)


def _report_input(game, report_type):
    profile = "advanced" if report_type == "deep" else report_type
    try:
        canonical = canonical_analysis_input(game.sgf_content, "report", profile)
        units = report_units(canonical["move_count"], profile)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_analysis_request", "message": str(exc)}) from exc
    return canonical, profile, units


def _reserve_report(db, *, user_id, game, report_type, body, trusted_free_eligible=False):
    canonical, profile, units = _report_input(game, report_type)
    try:
        op = billing_operations.reserve_operation_in_transaction(
            db,
            user_id=user_id,
            now=datetime.now(timezone.utc),
            kind="report",
            fingerprint=canonical["fingerprint"],
            profile=profile,
            units=units,
            environment=settings.KATRAIN_ENVIRONMENT,
            secret=settings.SECRET_KEY,
            quote_token=body.quote_token,
            idempotency_key=body.idempotency_key,
            membership_mode=settings.MEMBERSHIP_MODE,
            trusted_free_eligible=trusted_free_eligible,
            report_queue_limit=settings.MEMBERSHIP_REPORT_QUEUE_LIMIT,
            game_id=game.id,
        )
    except billing_operations.MembershipError as exc:
        raise _membership_http_error(exc) from exc
    # A library edit/delete can commit between the initial SGF read and the
    # admission lock. Freeze the current authoritative row before publishing work.
    fresh = (
        db.query(models_db.UserGame)
        .filter_by(id=game.id, user_id=user_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if fresh is None:
        raise HTTPException(status_code=404, detail="Game not found")
    current, _, _ = _report_input(fresh, report_type)
    if current["fingerprint"] != canonical["fingerprint"]:
        raise HTTPException(status_code=409, detail={"code": "quote_mismatch"})
    canonical = current
    return op, canonical


def _bind_paid_attempt(db, task, op, game, canonical):
    task.status, task.operation_id = "pending", op.id
    task.billing_version, task.model_sha256 = CATALOG_VERSION, op.model_sha256
    task.total_moves, task.analyzed_moves, task.settled_moves = canonical["move_count"], 0, 0
    task.analysis_sgf, task.sgf_hash = canonical["canonical_sgf"], sgf_fingerprint(game.sgf_content)
    task.generation = max(task.generation or 0, op.generation or 0)
    op.generation = task.generation
    task.retry_count, task.error_message = 0, None
    task.started_at, task.completed_at = None, None
    task.charge_ref, task.free_grant_period, task.billing_exempt_reason = None, None, None
    db.flush()
    op.task_id, op.game_id = task.id, game.id
    db.flush()


def _retry_original_legacy_authorization(db, *, task_id, user_id):
    """A migration may resume an unexpired old authorization, never issue another."""
    from katrain.web.core.membership import utc

    billing_operations.acquire_admission_lock(db)
    db.query(models_db.User).filter_by(id=user_id).with_for_update().populate_existing().one()
    task = (
        db.query(models_db.ReportTask)
        .filter_by(id=task_id, user_id=user_id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.REPORT_RETRY_GRACE_SEC)
    reserved = bool(task.charge_ref and billing.transaction_status(db, task.charge_ref) == "reserved")
    original_free = bool(
        task.free_grant_period
        and db.query(models_db.QuotaBucket.id)
        .filter(
            models_db.QuotaBucket.user_id == user_id,
            models_db.QuotaBucket.kind == "free_report",
            models_db.QuotaBucket.period_key == task.free_grant_period,
            models_db.QuotaBucket.used > 0,
        )
        .first()
    )
    if (
        is_membership_report(task)
        or task.status != "failed"
        or not task.updated_at
        or utc(task.updated_at) < cutoff
        or not (reserved or original_free)
    ):
        # Old expired reservations retain their original price and grace settlement.
        from katrain.web.core.report_settlement import settle_finished_reports

        settle_finished_reports(db, user_id=user_id)
        raise HTTPException(status_code=409, detail={"code": "legacy_report_requires_new_request"})
    try:
        billing_operations._check_slots(
            db,
            user_id=user_id,
            kind="report",
            report_queue_limit=settings.MEMBERSHIP_REPORT_QUEUE_LIMIT,
            position_queue_limit=settings.MEMBERSHIP_POSITION_QUEUE_LIMIT,
        )
    except billing_operations.MembershipError as exc:
        raise _membership_http_error(exc) from exc
    task.status, task.retry_count, task.error_message = "pending", 0, None
    task.started_at, task.completed_at = None, None
    task.generation = (task.generation or 0) + 1
    db.commit()
    return _task_to_dict(task)


def _existing_report_for_operation(db, op, *, user_id):
    try:
        original = billing_operations.resolve_owned_operation(db, op)
    except billing_operations.MembershipError as exc:
        raise _membership_http_error(exc) from exc
    existing = (
        db.query(models_db.ReportTask).filter_by(id=op.task_id, user_id=user_id, operation_id=original.id).first()
    )
    if existing is None:
        raise HTTPException(status_code=409, detail={"code": "report_attempt_superseded"})
    if original.status == "committed" and not membership_report_readable(db, existing, original):
        raise HTTPException(status_code=409, detail={"code": "report_result_unavailable"})
    return existing


def _create_paid_report(db, *, body, game, user_id, trusted_free_eligible=False):
    canonical, _, _ = _report_input(game, body.report_type)
    # A repeat view of an already owned report requires no fresh acceptance.
    # Do not bypass the operation identity check when a caller supplied a key.
    if not body.idempotency_key:
        for existing in (
            db.query(models_db.ReportTask)
            .filter_by(user_id=user_id, user_game_id=game.id, report_type=body.report_type, status="completed")
            .order_by(models_db.ReportTask.id.desc())
        ):
            original = db.get(models_db.BillingOperation, existing.operation_id) if existing.operation_id else None
            if (
                is_membership_report(existing)
                and original
                and original.fingerprint == canonical["fingerprint"]
                and membership_report_readable(db, existing, original)
            ):
                return _task_to_dict(existing)
        raise HTTPException(status_code=422, detail={"code": "quote_and_idempotency_required"})
    op, canonical = _reserve_report(
        db,
        user_id=user_id,
        game=game,
        report_type=body.report_type,
        body=body,
        trusted_free_eligible=trusted_free_eligible,
    )
    if op.task_id:
        existing = _existing_report_for_operation(db, op, user_id=user_id)
        db.commit()
        return _task_to_dict(existing, op)
    report = models_db.ReportTask(
        user_id=user_id,
        user_game_id=game.id,
        report_type=body.report_type,
        requested_visits=REPORT_VISITS[body.report_type],
        generation=0,
    )
    db.add(report)
    _bind_paid_attempt(db, report, op, game, canonical)
    db.commit()
    return _task_to_dict(report)


@router.post("/", response_model=ReportTaskStatus)
async def create_report_task(
    task: ReportTaskCreate,
    request: Request,
    current_user: User = Depends(require_writable_user),
    db: Session = Depends(get_report_db),
    trusted_free: bool = Depends(get_trusted_free_eligibility),
):
    guard_user_has_no_pending_ranked_game(request.app, current_user, "create report")
    if task.report_type not in REPORT_VISITS:
        raise HTTPException(status_code=400, detail="Unsupported report_type")

    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        return await _dispatch_remote_only(
            lambda: dispatcher.reports_create(task.model_dump(), expected_user_id=current_user.id)
        )

    game = (
        db.query(models_db.UserGame)
        .filter(
            models_db.UserGame.id == task.user_game_id,
            models_db.UserGame.user_id == current_user.id,
        )
        .first()
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if settings.MEMBERSHIP_MODE != "legacy" or _membership_user(db, current_user.id, app=request.app):
        return _create_paid_report(
            db, body=task, game=game, user_id=current_user.id, trusted_free_eligible=trusted_free
        )

    if not task.force:
        existing = (
            db.query(models_db.ReportTask)
            .filter(
                models_db.ReportTask.user_id == current_user.id,
                models_db.ReportTask.user_game_id == task.user_game_id,
                models_db.ReportTask.report_type == task.report_type,
                # "authorizing" 必须在这个集合里 —— 否则第二个并发请求会在第一个
                # 还在授权(计费)时穿过去重,造成两次真实扣费 + 两份 GPU 工作。
                models_db.ReportTask.status.in_(["authorizing", "pending", "running", "completed"]),
            )
            .order_by(models_db.ReportTask.created_at.desc(), models_db.ReportTask.id.desc())
            .first()
        )
        if existing:
            return _task_to_dict(existing)

    visits = REPORT_VISITS[task.report_type]

    if not settings.BILLING_ENFORCED:
        # 闸关着:行为与今天完全一致,一个字节都不改。
        report_task = models_db.ReportTask(
            user_id=current_user.id,
            user_game_id=task.user_game_id,
            report_type=task.report_type,
            requested_visits=visits,
            status="pending",
        )
        db.add(report_task)
        db.commit()
        db.refresh(report_task)
        return _task_to_dict(report_task)

    try:
        moves = count_moves(game.sgf_content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "unparsable_sgf", "message": str(exc)})

    cost = analysis_cost.report_cost(moves, visits)

    # 1) 先落成 authorizing —— cron 只按 status == "pending" 认领(report_analyze.py),
    #    这个状态它不会领走。计费落定之后(下面第 3 步)才翻成 pending 放给 cron,
    #    避免「先 pending 再计费」两次 commit 之间被 cron 抢跑、崩溃后留下已运行未计费的任务。
    report_task = models_db.ReportTask(
        user_id=current_user.id,
        user_game_id=task.user_game_id,
        report_type=task.report_type,
        requested_visits=visits,
        status="authorizing",
        total_moves=moves,
        sgf_hash=sgf_fingerprint(game.sgf_content),
    )
    db.add(report_task)
    db.commit()
    db.refresh(report_task)

    # 2) 先试免费周额度(不滚存,用掉就没);不够再扣积分。
    #
    # **顺序讲究**:两条路都是「先把意图落盘、再动钱」,不是反过来。
    # 反过来写(先动钱、再在内存里赋值、等第 3 步一起 commit)会开一个窗口:
    # 崩在中间时钱已经动了、任务上却没有 charge_ref / free_grant_period,
    # 于是结算器(按 charge_ref 遍历)找不到它、孤儿回收器(按任务行是否存在判断)
    # 也不退它 —— 积分被永久冻结、免费额度白白消失。
    # 现在这个顺序的崩溃方向是安全的:意图落了但钱没动,回收器去退一笔不存在的
    # 预扣(transaction_status 返回 None,跳过)或还一份没消费的额度
    # (release 的 `used >= n` 守卫挡住),都无副作用。
    period = quota.period_key("week")
    if task.report_type == "normal" and settings.FREE_WEEKLY_REPORTS > 0:
        report_task.free_grant_period = period
        db.commit()
        if quota.try_consume(db, current_user.id, "free_report:week", allowance=settings.FREE_WEEKLY_REPORTS):
            pass  # 免费额度拿到了,不扣积分
        else:
            report_task.free_grant_period = None
            db.commit()

    if report_task.free_grant_period is None:
        charge_ref = f"report:{report_task.id}"
        report_task.charge_ref = charge_ref
        db.commit()
        try:
            billing.reserve(db, current_user.id, cost, "report", charge_ref)
        except billing.InsufficientCredits:
            db.delete(report_task)
            db.commit()
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "insufficient_credits",
                    "need": cost,
                    "have": billing.get_balance(db, current_user.id),
                },
            )

    # 3) 计费落定之后才放给 cron。
    report_task.status = "pending"
    db.commit()
    db.refresh(report_task)
    return _task_to_dict(report_task)


@router.get("/", response_model=list[ReportTaskStatus])
async def list_report_tasks(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_report_db),
):
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        return await _dispatch_remote_only(lambda: dispatcher.reports_list(expected_user_id=current_user.id))

    tasks = (
        db.query(models_db.ReportTask)
        .filter(models_db.ReportTask.user_id == current_user.id)
        .order_by(models_db.ReportTask.created_at.desc(), models_db.ReportTask.id.desc())
        .all()
    )
    return [_task_to_dict(task) for task in tasks]


@router.get("/summary")
async def get_report_summary(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_report_db),
):
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        return await _dispatch_remote_only(lambda: dispatcher.reports_summary(expected_user_id=current_user.id))

    rows = (
        db.query(models_db.ReportTask.status, sa_func.count())
        .filter(models_db.ReportTask.user_id == current_user.id)
        .group_by(models_db.ReportTask.status)
        .all()
    )
    counts = {status: count for status, count in rows}
    return {
        "pending": counts.get("pending", 0),
        "running": counts.get("running", 0),
        "completed": counts.get("completed", 0),
        "failed": counts.get("failed", 0),
    }


@router.post("/{task_id}/retry", response_model=ReportTaskStatus)
async def retry_report_task(
    task_id: int,
    request: Request,
    body: ReportTaskRetry | None = None,
    current_user: User = Depends(require_writable_user),
    db: Session = Depends(get_report_db),
    trusted_free: bool = Depends(get_trusted_free_eligibility),
):
    guard_user_has_no_pending_ranked_game(request.app, current_user, "retry report")
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        return await _dispatch_remote_only(
            lambda: dispatcher.reports_retry(
                task_id, (body or ReportTaskRetry()).model_dump(), expected_user_id=current_user.id
            )
        )

    task = (
        db.query(models_db.ReportTask)
        .filter(
            models_db.ReportTask.id == task_id,
            models_db.ReportTask.user_id == current_user.id,
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Report task not found")
    if is_membership_report(task):
        body = body or ReportTaskRetry()
        if settings.MEMBERSHIP_MODE != "enabled":
            raise HTTPException(status_code=503, detail={"code": f"membership_{settings.MEMBERSHIP_MODE}"})
        # Admission lock must precede every user lock, including the old attempt's refund.
        billing_operations.acquire_admission_lock(db)
        task, old = _reconcile_paid_report(db, task_id=task.id, user_id=current_user.id)
        game = db.query(models_db.UserGame).filter_by(id=task.user_game_id, user_id=current_user.id).one_or_none()
        if game is None:
            raise HTTPException(status_code=404, detail="Game not found")
        # HTTP replay after a successful retry returns the same newly admitted attempt.
        if body.idempotency_key and old.idempotency_key == body.idempotency_key:
            _reserve_report(
                db,
                user_id=current_user.id,
                game=game,
                report_type=task.report_type,
                body=body,
                trusted_free_eligible=trusted_free,
            )
            db.commit()
            return _task_to_dict(task)
        if task.status != "failed" or old.status != "refunded":
            raise HTTPException(status_code=409, detail={"code": "report_not_retryable"})
        op, canonical = _reserve_report(
            db,
            user_id=current_user.id,
            game=game,
            report_type=task.report_type,
            body=body,
            trusted_free_eligible=trusted_free,
        )
        if op.task_id:
            existing = _existing_report_for_operation(db, op, user_id=current_user.id)
            db.commit()
            return _task_to_dict(existing, op)
        task.generation += 1
        db.query(models_db.ReportTaskMove).filter_by(task_id=task.id).delete(synchronize_session=False)
        _bind_paid_attempt(db, task, op, game, canonical)
        db.commit()
        return _task_to_dict(task)
    if settings.MEMBERSHIP_MODE == "paused":
        raise HTTPException(status_code=503, detail={"code": "membership_paused"})
    if settings.MEMBERSHIP_MODE == "enabled":
        return _retry_original_legacy_authorization(db, task_id=task.id, user_id=current_user.id)
    if _membership_user(db, current_user.id, app=request.app):
        raise HTTPException(status_code=503, detail={"code": "membership_legacy"})
    if task.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried")

    # 计费闸开着、这个任务当初是走积分扣费的(不是免费周额度)、且它的预扣已经
    # 被结算器清掉(charge_ref 变 None) —— 只可能是 settle_finished_reports 在
    # 宽限期(REPORT_RETRY_GRACE_SEC)之后把它结清了。这时候原预扣已经不存在,
    # 继续按"改回 pending"处理就是让用户免费续跑剩余手数。必须为剩余量重新预扣。
    #
    # 免费周额度(free_grant_period != None)不在这条判断里 —— 那笔额度从建任务
    # 起就只消费一次,重试同一个任务不应该、也不会再扣第二次。
    if settings.BILLING_ENFORCED and task.charge_ref is None and task.free_grant_period is None:
        remaining = max(0, (task.total_moves or 0) - (task.analyzed_moves or 0))
        cost = analysis_cost.report_cost(remaining, task.requested_visits or 0)
        # 不能复用原 `report:{id}`：那笔已经 committed，billing.reserve 的幂等判断
        # 会直接放行、不扣钱 —— 等于白送一次重试。每次重新授权开一个新的确定性 ref。
        n = 1
        base_ref = f"report:{task.id}"
        while billing.has_transaction(db, f"{base_ref}:retry{n}"):
            n += 1
        new_ref = f"{base_ref}:retry{n}"

        # **先落意图、再动钱** —— 与建任务路径同形（见 create_report_task 里那段注释）。
        # 反过来写会开一个没有任何管理者的窗口：billing.reserve 内部自己 commit,
        # 钱当场落盘;若在它与最终 db.commit() 之间断连/锁超时,任务上就没有 charge_ref,
        # 而四个管理者一个都够不着 ——
        #   结算器顶层过滤 charge_ref.isnot(None)
        #   孤儿回收器看见任务行还在就跳过
        #   滞留回收器只收 status == "authorizing",这个任务是 failed
        #   通用 TTL 回收器被 LONG_RUNNING_REASONS 排除
        # 那笔预扣就永久冻结。终审用 probe_retry_frozen.py 实测过这条。
        task.charge_ref = new_ref
        db.commit()
        try:
            billing.reserve(db, current_user.id, cost, "report", new_ref)
        except billing.InsufficientCredits:
            # 意图落了但钱没动 —— 把引用摘掉,别让任务指着一笔不存在的预扣。
            task.charge_ref = None
            db.commit()
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "insufficient_credits",
                    "need": cost,
                    "have": billing.get_balance(db, current_user.id),
                },
            )

    task.status = "pending"
    task.retry_count = 0
    task.error_message = None
    # Both stamps, not just `completed_at`. A failed task can sit here for a night before
    # anyone presses retry; leaving the old `started_at` would make the next completion
    # report a span that covers the waiting, and the screen would read "took 14 hours"
    # for six minutes of analysis. Cleared here, the cron worker re-stamps it on claim.
    task.started_at = None
    task.completed_at = None
    db.commit()
    db.refresh(task)
    return _task_to_dict(task)


@router.get("/{task_id}", response_model=ReportTaskStatus)
async def get_report_status(
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_report_db),
):
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        return await _dispatch_remote_only(lambda: dispatcher.reports_get(task_id, expected_user_id=current_user.id))

    task = (
        db.query(models_db.ReportTask)
        .filter(
            models_db.ReportTask.id == task_id,
            models_db.ReportTask.user_id == current_user.id,
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Report task not found")
    if is_membership_report(task):
        task, _ = _reconcile_paid_report(db, task_id=task.id, user_id=current_user.id)
        db.commit()
    return _task_to_dict(task)


@router.get("/{task_id}/moves", response_model=list[ReportTaskMoveResponse])
async def get_report_moves(
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_report_db),
):
    guard_user_has_no_pending_ranked_game(request.app, current_user, "report analysis")
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        return await _dispatch_remote_only(lambda: dispatcher.reports_moves(task_id, expected_user_id=current_user.id))

    task = (
        db.query(models_db.ReportTask)
        .filter(
            models_db.ReportTask.id == task_id,
            models_db.ReportTask.user_id == current_user.id,
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Report task not found")

    if is_membership_report(task):
        task, op = _reconcile_paid_report(db, task_id=task.id, user_id=current_user.id)
        db.commit()
        if not membership_report_readable(db, task, op):
            raise HTTPException(status_code=409, detail={"code": "report_not_committed"})

    moves = (
        db.query(models_db.ReportTaskMove)
        .filter(models_db.ReportTaskMove.task_id == task_id)
        .order_by(models_db.ReportTaskMove.move_number.asc(), models_db.ReportTaskMove.id.asc())
        .all()
    )
    return _moves_with_grades(moves)
