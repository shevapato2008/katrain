"""Read-only cron status, run history, and queue summaries for the admin app."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from katrain.web.admin.cron_health import as_utc, derive_health
from katrain.web.admin.cron_schemas import (
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

    jobs = []
    for row in rows:
        health = derive_health(row, observed_at)
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
            )
        )
    return CronJobsResponse(observed_at=observed_at, jobs=jobs)


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
