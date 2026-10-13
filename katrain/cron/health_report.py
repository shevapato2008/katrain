"""Cron's copy of the config check (the cron image only ships `katrain/cron/`).

Same verdict shape and rules as `katrain/web/core/health_report.py`; messages are templates and
never contain configuration values. Written to the web-owned `process_health_reports` table.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from urllib.parse import urlparse
from datetime import datetime, timezone

INTERVAL_S = 600
log = logging.getLogger("katrain_cron.health_report")


def build_id() -> str:
    return (os.getenv("KATRAIN_BUILD_SHA") or "unknown").strip()[:64] or "unknown"


def _run(rules) -> list:
    checks = []
    for check_id, rule in rules:
        try:
            level, message = rule()
        except Exception:
            level, message = "unknown", "这项检查本身出错，结论未知"
        checks.append({"id": check_id, "level": level, "message": message})
    return checks


def cron_checks(c) -> list:
    def katago():
        if not c.KATAGO_URL:
            return "bad", "未配置分析引擎地址：复盘与直播分析无法运行"
        host = (urlparse(c.KATAGO_URL).hostname or "").lower()
        if host in ("127.0.0.1", "localhost", "::1") and os.path.exists("/.dockerenv"):
            return "warn", "分析引擎地址指向容器自身的回环地址（通常是没配 KATAGO_URL 的默认值）"
        return "ok", "已配置分析引擎地址"

    return _run(
        [
            ("database", lambda: ("bad", "数据库是 SQLite：不是共享主库") if str(c.DATABASE_URL).startswith("sqlite") else ("ok", "PostgreSQL 主库")),
            ("katago", katago),
            ("translation", lambda: ("ok", "已配置翻译服务密钥") if c.DASHSCOPE_API_KEY else ("warn", "未配置翻译服务密钥：直播名称翻译失效")),
            ("credentials", lambda: ("bad", "数据库密码仍是示例默认值") if "CHANGE_ME" in str(c.DATABASE_URL) else ("ok", "未使用示例默认密码")),
        ]
    )


def write_report(checks: list, extra: dict | None = None) -> bool:
    from katrain.cron.db import SessionLocal
    from katrain.cron.models import ProcessHealthReportDB

    try:
        with SessionLocal() as db:
            db.merge(
                ProcessHealthReportDB(
                    process="cron",
                    hostname=socket.gethostname()[:128],
                    build=build_id(),
                    generated_at=datetime.now(timezone.utc),
                    report=json.dumps({"checks": checks, **(extra or {})}, ensure_ascii=False),
                )
            )
            db.commit()
        return True
    except Exception as exc:
        log.warning("health report write failed: %s", type(exc).__name__)
        return False


async def report_forever(shutdown: asyncio.Event, interval: float = INTERVAL_S, extra=None) -> None:
    from katrain.cron import config

    while not shutdown.is_set():
        written = await asyncio.to_thread(write_report, cron_checks(config), extra() if extra else None)
        try:
            await asyncio.wait_for(shutdown.wait(), timeout=interval if written else 30)
        except asyncio.TimeoutError:
            pass
