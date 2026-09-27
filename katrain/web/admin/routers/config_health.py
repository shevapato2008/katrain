"""Config check view: per-process verdict rows plus cross-process checks, with honest staleness.

A process with no row is `never` (bad); a row older than STALE_AFTER is `stale` and its verdicts
are withheld (only its time is shown); cross-process checks only count fresh rows, and an
`unknown` build never reads as consistent.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from katrain.web.admin.cron_health import as_utc
from katrain.web.admin.routers.tutorials import get_admin_db
from katrain.web.admin.session import get_current_admin
from katrain.web.core.models_db import ProcessHealthReport

router = APIRouter(dependencies=[Depends(get_current_admin)])
PROCESSES = ("web", "cron", "admin")
STALE_AFTER_S = 30 * 60


def _checks(raw: str) -> tuple[list, dict]:
    try:
        body = json.loads(raw)
    except ValueError:
        body = None
    if not isinstance(body, dict):
        return [{"id": "report", "level": "unknown", "message": "上报内容无法解析"}], {}
    checks = [c for c in body.get("checks", []) if isinstance(c, dict)]
    return checks, {k: v for k, v in body.items() if k != "checks"}


@router.get("/config-health")
def config_health(db: Session = Depends(get_admin_db)):
    now = datetime.now(timezone.utc)
    rows = {row.process: row for row in db.scalars(select(ProcessHealthReport)).all()}
    processes, fresh_builds = [], {}
    for name in PROCESSES:
        row = rows.get(name)
        if row is None:
            processes.append({"process": name, "state": "never", "hostname": None, "build": None, "generated_at": None, "age_s": None, "checks": [], "extra": {}})
            continue
        age = (now - as_utc(row.generated_at)).total_seconds()
        stale = age > STALE_AFTER_S
        checks, extra = _checks(row.report)
        if not stale:
            fresh_builds[name] = row.build
        processes.append(
            {
                "process": name,
                "state": "stale" if stale else "fresh",
                "hostname": row.hostname,
                "build": row.build,
                "generated_at": as_utc(row.generated_at).isoformat(),
                "age_s": round(age),
                "checks": [] if stale else checks,
                "extra": {} if stale else extra,
            }
        )
    if len(fresh_builds) < len(PROCESSES):
        version = {"level": "unknown", "message": "不是每个进程都有新近上报，无法比较版本"}
    elif "unknown" in fresh_builds.values():
        version = {"level": "unknown", "message": "有进程没有上报构建版本（未设 KATRAIN_BUILD_SHA）"}
    elif len(set(fresh_builds.values())) > 1:
        version = {"level": "warn", "message": "三个进程运行的构建版本不一致"}
    else:
        version = {"level": "ok", "message": f"三个进程运行同一构建版本 {next(iter(fresh_builds.values()))}"}
    return {
        "observed_at": now.isoformat(),
        "stale_after_s": STALE_AFTER_S,
        "processes": processes,
        "cross_checks": [{"id": "build_consistency", **version}],
    }
