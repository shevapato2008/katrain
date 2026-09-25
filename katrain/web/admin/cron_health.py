"""Derive cron health at the admin API's observation time."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


OFFLINE_AFTER = timedelta(seconds=120)
LOOP_STUCK_AFTER = timedelta(seconds=300)
LOOP_ERRORS_WINDOW = timedelta(minutes=10)
INTERVAL_STUCK_FLOOR = timedelta(seconds=600)
OVERDUE_GRACE = timedelta(seconds=60)


@dataclass(frozen=True)
class Health:
    state: str
    reason: str


def as_utc(dt: datetime | None) -> datetime | None:
    """Treat SQLite's naive datetimes as UTC and normalize aware datetimes."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return as_utc(datetime.fromisoformat(value))
    except ValueError:
        return None


def _human(delta: timedelta) -> str:
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return f"{seconds} 秒"
    if seconds < 3600:
        return f"{seconds // 60} 分钟"
    if seconds < 86400:
        return f"{seconds // 3600} 小时"
    return f"{seconds // 86400} 天"


def derive_health(row, now: datetime) -> Health:
    """Apply the spec's health states in priority order, stopping at the first match."""
    now = as_utc(now)
    heartbeat = as_utc(row.heartbeat_at)
    if heartbeat is None:
        return Health("offline", "cron 进程从未上报心跳")
    if now - heartbeat > OFFLINE_AFTER:
        return Health("offline", f"cron 进程失联：{_human(now - heartbeat)}没有心跳")
    if not row.enabled:
        return Health("disabled", "已被配置停用")

    if row.kind == "loop":
        iteration = as_utc(row.loop_iteration_at)
        if iteration is None:
            return Health("pending", "进程启动后循环还没有推进过")
        if now - iteration > LOOP_STUCK_AFTER:
            return Health("stuck", f"循环已经 {_human(now - iteration)}没有推进")
        if row.last_status == "failed":
            return Health("failed", "循环刚崩溃，正在重启")
        last_error = _parse_timestamp((row.loop_stats or {}).get("last_error_at"))
        if last_error is not None and now - last_error <= LOOP_ERRORS_WINDOW:
            return Health("errors", f"{_human(now - last_error)}前有报错")
        return Health("ok", f"循环 {_human(now - iteration)}前推进过")

    interval = timedelta(seconds=row.interval_seconds or 0)
    started = as_utc(row.last_started_at)
    if started is None:
        return Health("pending", "进程启动后还没有运行过")
    elapsed = now - started
    if row.last_status == "running":
        limit = max(3 * interval, INTERVAL_STUCK_FLOOR)
        if elapsed > limit:
            return Health("stuck", f"已运行 {_human(elapsed)}，超过了 {_human(limit)}")
        return Health("running", f"已运行 {_human(elapsed)}")
    if row.last_status == "failed":
        return Health("failed", f"连续 {row.consecutive_failures} 次不成功，最近一次抛出了异常")
    if row.last_status == "errors":
        return Health("errors", "跑完了，但运行期间有报错")
    if elapsed > 2 * interval + OVERDUE_GRACE:
        return Health("overdue", f"上次开始于 {_human(elapsed)}前，间隔是 {_human(interval)}")
    return Health("ok", f"上次开始于 {_human(elapsed)}前")
