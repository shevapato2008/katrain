"""Error groups collected from web / cron / admin, the resolve action, and the nav attention badge."""

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from katrain.web.admin.cron_health import as_utc
from katrain.web.admin.routers.config_health import evaluate
from katrain.web.admin.routers.tutorials import get_admin_db
from katrain.web.admin.session import get_current_admin
from katrain.web.core.models_db import AdminAuditLog, ErrorGroup

router = APIRouter(dependencies=[Depends(get_current_admin)])
ATTENTION_WINDOW = timedelta(hours=24)


def _iso(value):
    return as_utc(value).isoformat() if value is not None else None


def _row(g: ErrorGroup) -> dict:
    return {
        "id": g.id, "process": g.process, "logger": g.logger, "exc_type": g.exc_type, "template": g.template,
        "location": g.location, "job": g.job, "first_seen": _iso(g.first_seen), "last_seen": _iso(g.last_seen),
        "state_changed_at": _iso(g.state_changed_at), "count": g.count, "sample": g.sample, "build": g.build,
        "resolved_at": _iso(g.resolved_at), "resolved_by": g.resolved_by,
    }


@router.get("/errors")
def list_errors(
    process: str | None = Query(None, pattern="^(web|cron|admin)$"),
    status: str = Query("open", pattern="^(open|resolved|all)$"),
    page: int = Query(1, ge=1, le=1000),
    db: Session = Depends(get_admin_db),
):
    page_size = 30
    query = select(ErrorGroup)
    if process:
        query = query.where(ErrorGroup.process == process)
    if status == "open":
        query = query.where(ErrorGroup.resolved_at.is_(None))
    elif status == "resolved":
        query = query.where(ErrorGroup.resolved_at.is_not(None))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(ErrorGroup.last_seen.desc(), ErrorGroup.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    collectors = {}
    for item in evaluate(db)["processes"]:
        collectors[item["process"]] = {"state": item["state"], "age_s": item["age_s"], **(item["extra"].get("collector") or {})}
    return {"items": [_row(g) for g in rows], "total": total, "page": page, "page_size": page_size, "collectors": collectors}


@router.post("/errors/{group_id}/resolve")
def resolve_error(group_id: int, admin: dict = Depends(get_current_admin), db: Session = Depends(get_admin_db)):
    group = db.get(ErrorGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="报错分组不存在")
    if group.resolved_at is None:
        now = datetime.now(timezone.utc)
        group.resolved_at, group.resolved_by, group.state_changed_at = now, admin["username"], now
        db.add(
            AdminAuditLog(
                actor_realm="admin", actor_username=admin["username"], action="error_resolve", target_type="error_group",
                target_id=group.id, success=True,
                detail=json.dumps({"process": group.process, "template": group.template[:200], "count": group.count}, ensure_ascii=False),
            )
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    return _row(group)


@router.get("/attention")
def attention(db: Session = Depends(get_admin_db)):
    """Badge counts: error groups new or reopened in the last 24 h, and config problems."""
    since = datetime.now(timezone.utc) - ATTENTION_WINDOW
    errors = db.scalar(
        select(func.count()).select_from(ErrorGroup).where(ErrorGroup.resolved_at.is_(None), ErrorGroup.state_changed_at >= since)
    )
    health = evaluate(db)
    config = sum(1 for p in health["processes"] if p["state"] == "never") + sum(
        1 for p in health["processes"] if p["state"] == "fresh" for c in p["checks"] if c.get("level") == "bad"
    )
    return {"errors": errors, "config": config}
