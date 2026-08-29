from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.core import move_grade
from katrain.web.core import models_db
from katrain.web.core.db import SessionLocal
from katrain.web.core.repository import RemoteServiceUnavailableError
from katrain.web.models import User

router = APIRouter()

REPORT_VISITS = {
    "normal": 500,
    "deep": 2000,
}


class ReportTaskCreate(BaseModel):
    user_game_id: str
    report_type: str = "normal"
    force: bool = False


class ReportTaskStatus(BaseModel):
    id: int
    user_game_id: str
    status: str
    report_type: str
    total_moves: int
    analyzed_moves: int
    requested_visits: int


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


def _task_to_dict(task: models_db.ReportTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "user_game_id": task.user_game_id,
        "status": task.status,
        "report_type": task.report_type,
        "total_moves": task.total_moves,
        "analyzed_moves": task.analyzed_moves,
        "requested_visits": task.requested_visits,
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


@router.post("/", response_model=ReportTaskStatus)
async def create_report_task(
    task: ReportTaskCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_report_db),
):
    if task.report_type not in REPORT_VISITS:
        raise HTTPException(status_code=400, detail="Unsupported report_type")

    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        return await _dispatch_remote_only(lambda: dispatcher.reports_create(task.model_dump()))

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

    if not task.force:
        existing = (
            db.query(models_db.ReportTask)
            .filter(
                models_db.ReportTask.user_id == current_user.id,
                models_db.ReportTask.user_game_id == task.user_game_id,
                models_db.ReportTask.report_type == task.report_type,
                models_db.ReportTask.status.in_(["pending", "running", "completed"]),
            )
            .order_by(models_db.ReportTask.created_at.desc(), models_db.ReportTask.id.desc())
            .first()
        )
        if existing:
            return _task_to_dict(existing)

    report_task = models_db.ReportTask(
        user_id=current_user.id,
        user_game_id=task.user_game_id,
        report_type=task.report_type,
        requested_visits=REPORT_VISITS[task.report_type],
        status="pending",
    )
    db.add(report_task)
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
        return await _dispatch_remote_only(dispatcher.reports_list)

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
        return await _dispatch_remote_only(dispatcher.reports_summary)

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_report_db),
):
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        return await _dispatch_remote_only(lambda: dispatcher.reports_retry(task_id))

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
    if task.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried")
    task.status = "pending"
    task.retry_count = 0
    task.error_message = None
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
        return await _dispatch_remote_only(lambda: dispatcher.reports_get(task_id))

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
    return _task_to_dict(task)


@router.get("/{task_id}/moves", response_model=list[ReportTaskMoveResponse])
async def get_report_moves(
    task_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_report_db),
):
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        return await _dispatch_remote_only(lambda: dispatcher.reports_moves(task_id))

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

    moves = (
        db.query(models_db.ReportTaskMove)
        .filter(models_db.ReportTaskMove.task_id == task_id)
        .order_by(models_db.ReportTaskMove.move_number.asc(), models_db.ReportTaskMove.id.asc())
        .all()
    )
    return _moves_with_grades(moves)
