"""Config check: each process writes templated verdicts about its own effective configuration.

A verdict is `{"id", "level", "message"}` with level ok / warn / bad / unknown. Messages come
from fixed templates and never contain configuration values (a secret must not reach the table).
A rule that raises becomes `unknown`, never `ok`. The cron image cannot import this module (it
only copies `katrain/cron/`), so cron keeps its own copy in `katrain/cron/health_report.py`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from datetime import datetime, timezone

INTERVAL_S = 600
log = logging.getLogger("katrain.health_report")


def build_id() -> str:
    return (os.getenv("KATRAIN_BUILD_SHA") or "unknown").strip()[:64] or "unknown"


def _run(rules) -> list[dict]:
    checks = []
    for check_id, rule in rules:
        try:
            level, message = rule()
        except Exception:
            level, message = "unknown", "这项检查本身出错，结论未知"
        checks.append({"id": check_id, "level": level, "message": message})
    return checks


def database_rule(url):
    return ("bad", "数据库是 SQLite：不是共享主库") if str(url).startswith("sqlite") else ("ok", "PostgreSQL 主库")


def credentials_rule(*secrets):
    if any("CHANGE_ME" in str(value) for value in secrets):
        return "bad", "数据库或对象存储密码仍是示例默认值"
    return "ok", "未使用示例默认密码"


def web_checks(s) -> list[dict]:
    def billing():
        if not s.BILLING_ENFORCED:
            return "ok", "计费闸关闭：复盘报告免费"
        if int(s.FREE_WEEKLY_REPORTS) > 0:
            return "bad", "计费闸已开但每周免费报告不为 0（手机绑定与限流未上线前必须为 0）"
        return "ok", "计费闸已开，每周免费报告为 0"

    return _run(
        [
            ("database", lambda: database_rule(s.DATABASE_URL)),
            ("billing", billing),
            ("storage", lambda: ("warn", "媒体存本机磁盘，不是对象存储") if s.STORAGE_BACKEND == "local" else ("ok", "媒体存对象存储")),
            ("credentials", lambda: credentials_rule(s.DATABASE_URL, s.S3_SECRET_KEY)),
        ]
    )


def admin_checks(s) -> list[dict]:
    return _run(
        [
            ("database", lambda: database_rule(s.DATABASE_URL)),
            ("credentials", lambda: credentials_rule(s.DATABASE_URL, s.S3_SECRET_KEY)),
        ]
    )


def write_report(session_factory, process: str, checks: list[dict], extra: dict | None = None) -> bool:
    """Upsert this process's row. Failures are logged as warnings and never raised."""
    from katrain.web.core.models_db import ProcessHealthReport

    try:
        with session_factory() as db:
            db.merge(
                ProcessHealthReport(
                    process=process,
                    hostname=socket.gethostname()[:128],
                    build=build_id(),
                    generated_at=datetime.now(timezone.utc),
                    report=json.dumps({"checks": checks, **(extra or {})}, ensure_ascii=False),
                )
            )
            db.commit()
        return True
    except Exception as exc:  # the report is advisory; never take the process down
        log.warning("health report write failed: %s", type(exc).__name__)
        return False


RETRY_S = 30


async def report_forever(session_factory, process: str, make_checks, interval: float = INTERVAL_S, extra=None):
    """Write now and every `interval`; a failed write (e.g. the table is not created yet because web
    has not finished init_db) is retried once after RETRY_S instead of waiting a full interval."""
    while True:
        written = await asyncio.to_thread(write_report, session_factory, process, make_checks(), extra() if extra else None)
        await asyncio.sleep(RETRY_S if not written else interval)
