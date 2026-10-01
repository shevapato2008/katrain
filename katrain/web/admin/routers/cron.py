"""Read-only cron status, run history, and queue summaries for the admin app."""

from datetime import datetime, timezone

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from katrain.web.admin.cron_health import as_utc, derive_health
from katrain.web.admin.cron_schemas import (
    CronCommandOut,
    CronHealthOut,
    CronJobOut,
    CronJobsResponse,
    CronQueueOut,
    CronQueuesResponse,
    CronRunOut,
    CronRunsResponse,
)
from katrain.web.admin.session import get_current_admin
from katrain.web.core import models_db


router = APIRouter(dependencies=[Depends(get_current_admin)])
TABLES_MISSING = "cron 状态表不存在：katrain-web 新版本还没启动过"
RUNS_TABLE_MISSING = "cron 运行记录表不存在：katrain-web 新版本还没启动过"
DATABASE_UNAVAILABLE = "cron 数据库暂时不可用"


def _database_error(exc: DBAPIError) -> HTTPException:
    original = exc.orig
    message = str(original).lower()
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    missing_table = sqlstate == "42P01" or "no such table:" in message
    if missing_table:
        table = getattr(getattr(original, "diag", None), "table_name", None)
        table_name = str(table or message).lower()
        if "cron_job_status" in table_name:
            return HTTPException(status_code=503, detail=TABLES_MISSING)
        if "cron_job_runs" in table_name:
            return HTTPException(status_code=503, detail=RUNS_TABLE_MISSING)
    return HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE)


@router.get("/jobs", response_model=CronJobsResponse)
def list_jobs(request: Request) -> CronJobsResponse:
    observed_at = datetime.now(timezone.utc)
    try:
        with request.app.state.session_factory() as db:
            rows = db.scalars(select(models_db.CronJobStatus).order_by(models_db.CronJobStatus.job_name)).all()
    except DBAPIError as exc:
        raise _database_error(exc) from exc

    controls, pending, latest = _controls(request)
    jobs = []
    for row in rows:
        control = controls.get(row.job_name)
        paused = control is not None and control.paused
        health = derive_health(
            row, observed_at, (control.reason or "") if paused else None, control.changed_at if control is not None and not paused else None
        )
        jobs.append(
            CronJobOut(
                name=row.job_name,
                kind=row.kind,
                interval_seconds=row.interval_seconds,
                enabled=row.enabled,
                health=CronHealthOut(state=health.state, reason=health.reason),
                process_started_at=as_utc(row.process_started_at),
                heartbeat_at=as_utc(row.heartbeat_at),
                last_started_at=as_utc(row.last_started_at),
                last_finished_at=as_utc(row.last_finished_at),
                last_success_at=as_utc(row.last_success_at),
                last_status=row.last_status,
                last_duration_ms=row.last_duration_ms,
                last_error=row.last_error,
                consecutive_failures=row.consecutive_failures or 0,
                loop_iteration_at=as_utc(row.loop_iteration_at),
                loop_stats=row.loop_stats,
                paused=paused,
                pause_reason=control.reason if paused else None,
                paused_by=control.changed_by if paused else None,
                paused_at=as_utc(control.changed_at) if paused else None,
                pending_run=_command_out(pending.get(row.job_name)),
                last_command=_command_out(latest.get(row.job_name)),
            )
        )
    return CronJobsResponse(observed_at=observed_at, jobs=jobs)


def _controls(request: Request):
    """Pause state and commands. The control tables may predate a web upgrade: then nothing is paused."""
    try:
        with request.app.state.session_factory() as db:
            controls = {c.job_name: c for c in db.scalars(select(models_db.CronJobControl)).all()}
            waiting = db.scalars(select(models_db.CronJobCommand).where(models_db.CronJobCommand.state == "pending")).all()
            commands = list(waiting) + list(db.scalars(select(models_db.CronJobCommand).order_by(models_db.CronJobCommand.id.desc()).limit(200)).all())
            db.expunge_all()
    except DBAPIError:
        return {}, {}, {}
    pending, latest = {}, {}
    for command in sorted(commands, key=lambda c: c.id, reverse=True):
        latest.setdefault(command.job_name, command)
        if command.state == "pending":
            pending.setdefault(command.job_name, command)
    return controls, pending, latest


def _command_out(command) -> CronCommandOut | None:
    if command is None:
        return None
    return CronCommandOut(
        id=command.id, state=command.state, requested_at=as_utc(command.requested_at), requested_by=command.requested_by,
        handled_at=as_utc(command.handled_at), note=command.note,
    )


class PauseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(max_length=200)

    @field_validator("reason")
    @classmethod
    def meaningful(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("reason needs at least 5 characters")
        return value


def _audit(db, admin: dict, action: str, name: str, detail: dict) -> None:
    db.add(
        models_db.AdminAuditLog(
            actor_realm="admin", actor_username=admin["username"], action=action, target_type="cron_job",
            target_id=None, success=True, detail=json.dumps({"job": name, **detail}, ensure_ascii=False),
        )
    )


def _interval_job(db, name: str):
    row = db.get(models_db.CronJobStatus, name)
    if row is None:
        raise HTTPException(status_code=404, detail="没有这个任务")
    if row.kind != "interval":
        raise HTTPException(status_code=409, detail="常驻循环任务不支持暂停或立即运行")
    return row


def _commit(db) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


@router.post("/jobs/{name}/pause")
def pause_job(name: str, body: PauseRequest, request: Request, admin: dict = Depends(get_current_admin)):
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory() as db:
        _interval_job(db, name)
        control = db.get(models_db.CronJobControl, name)
        if control is not None and control.paused:
            raise HTTPException(status_code=409, detail="任务已经是暂停状态")
        if control is None:
            control = models_db.CronJobControl(job_name=name, changed_at=now, changed_by=admin["username"])
            db.add(control)
        control.paused, control.reason, control.changed_at, control.changed_by = True, body.reason, now, admin["username"]
        _audit(db, admin, "cron_pause", name, {"reason": body.reason})
        _commit(db)
    return {"job": name, "paused": True}


@router.post("/jobs/{name}/resume")
def resume_job(name: str, request: Request, admin: dict = Depends(get_current_admin)):
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory() as db:
        _interval_job(db, name)
        control = db.get(models_db.CronJobControl, name)
        if control is None or not control.paused:
            raise HTTPException(status_code=409, detail="任务没有暂停")
        control.paused, control.changed_at, control.changed_by = False, now, admin["username"]
        _audit(db, admin, "cron_resume", name, {"reason": control.reason})
        _commit(db)
    return {"job": name, "paused": False}


@router.post("/jobs/{name}/run")
def run_job_now(name: str, request: Request, admin: dict = Depends(get_current_admin)):
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory() as db:
        row = _interval_job(db, name)
        if not row.enabled:
            raise HTTPException(status_code=409, detail="任务已被配置停用，cron 不会调度它")
        control = db.get(models_db.CronJobControl, name)
        if control is not None and control.paused:
            raise HTTPException(status_code=409, detail="任务已暂停，先恢复再运行")
        waiting = db.scalar(
            select(models_db.CronJobCommand).where(models_db.CronJobCommand.job_name == name, models_db.CronJobCommand.state == "pending")
        )
        if waiting is not None:
            raise HTTPException(status_code=409, detail="已有一条立即运行在排队，等 cron 领取")
        command = models_db.CronJobCommand(job_name=name, command="run_now", requested_at=now, requested_by=admin["username"], state="pending")
        db.add(command)
        _audit(db, admin, "cron_run_now", name, {})
        _commit(db)
        return {"id": command.id, "job": name, "state": "pending"}


@router.get("/jobs/{name}/runs", response_model=CronRunsResponse)
def list_runs(
    request: Request,
    name: str,
    limit: int = Query(50, ge=1, le=200),
    before_id: int | None = Query(None, ge=1),
) -> CronRunsResponse:
    try:
        with request.app.state.session_factory() as db:
            if db.get(models_db.CronJobStatus, name) is None:
                raise HTTPException(status_code=404, detail="没有这个任务")
            query = select(models_db.CronJobRun).where(models_db.CronJobRun.job_name == name)
            if before_id is not None:
                query = query.where(models_db.CronJobRun.id < before_id)
            rows = db.scalars(query.order_by(models_db.CronJobRun.id.desc()).limit(limit + 1)).all()
    except DBAPIError as exc:
        raise _database_error(exc) from exc

    page = rows[:limit]
    return CronRunsResponse(
        runs=[
            CronRunOut(
                id=row.id,
                started_at=as_utc(row.started_at),
                finished_at=as_utc(row.finished_at),
                status=row.status,
                duration_ms=row.duration_ms,
                error_count=row.error_count or 0,
                error=row.error,
            )
            for row in page
        ],
        next_before_id=page[-1].id if len(rows) > limit else None,
    )


def _queue(db, status_column, created_column) -> CronQueueOut:
    counts = db.execute(select(status_column, func.count()).group_by(status_column)).all()
    oldest = db.scalar(select(func.min(created_column)).where(status_column == "pending"))
    return CronQueueOut(by_status={str(status): count for status, count in counts}, oldest_pending_at=as_utc(oldest))


@router.get("/queues", response_model=CronQueuesResponse)
def list_queues(request: Request) -> CronQueuesResponse:
    observed_at = datetime.now(timezone.utc)
    try:
        with request.app.state.session_factory() as db:
            live = _queue(db, models_db.LiveAnalysisDB.status, models_db.LiveAnalysisDB.created_at)
            reports = _queue(db, models_db.ReportTask.status, models_db.ReportTask.created_at)
    except DBAPIError as exc:
        raise _database_error(exc) from exc
    return CronQueuesResponse(observed_at=observed_at, live_analysis=live, report_tasks=reports)
