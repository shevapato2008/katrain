from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.core import models_db
from katrain.web.core.db import SessionLocal
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
    }


@router.post("/", response_model=ReportTaskStatus)
async def create_report_task(
    task: ReportTaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_report_db),
):
    if task.report_type not in REPORT_VISITS:
        raise HTTPException(status_code=400, detail="Unsupported report_type")

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_report_db),
):
    tasks = (
        db.query(models_db.ReportTask)
        .filter(models_db.ReportTask.user_id == current_user.id)
        .order_by(models_db.ReportTask.created_at.desc(), models_db.ReportTask.id.desc())
        .all()
    )
    return [_task_to_dict(task) for task in tasks]


@router.get("/summary")
async def get_report_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_report_db),
):
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_report_db),
):
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_report_db),
):
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_report_db),
):
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
    return [_move_to_dict(move) for move in moves]
