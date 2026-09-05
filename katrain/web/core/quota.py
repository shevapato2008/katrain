# katrain/web/core/quota.py
"""额度桶：惰性周期键 + 原子消费。

**为什么没有重置任务**：周期到点会自然生成一个新的 period_key，
旧桶原地不动、新桶从 0 开始。任何"到点把 used 清零"的定时任务都是多余的，
而且一旦漏跑就会静默地让用户少领一轮。

**限制**：本切片只支持 day / week / month 三种自然周期。requirements.md 提到的
`P:<subscription_period_id>`（按订阅日切）**没有实现** —— 套餐上线时补，
届时要处理非自然月续费、取消与降级。
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from katrain.web.core import models_db

# 计费周期一律按北京时间切，不跟服务器时区走。
BILLING_TZ = timezone(timedelta(hours=8))


def period_key(kind_period: str, now: Optional[datetime] = None) -> str:
    """把时间点映射到周期键。kind_period ∈ {day, week, month}。"""
    t = (now or datetime.now(timezone.utc)).astimezone(BILLING_TZ)
    if kind_period == "day":
        return f"D:{t:%Y-%m-%d}"
    if kind_period == "week":
        iso_year, iso_week, _ = t.isocalendar()
        return f"W:{iso_year}-W{iso_week:02d}"
    if kind_period == "month":
        return f"M:{t:%Y-%m}"
    raise ValueError(f"未知周期 {kind_period!r}（本切片只支持 day/week/month）")


def _split(kind: str) -> Tuple[str, str]:
    """'free_report:week' -> ('free_report', 'week')"""
    name, _, period = kind.partition(":")
    if not period:
        raise ValueError(f"kind 必须形如 'name:period'，收到 {kind!r}")
    return name, period


def _ensure_bucket(db: Session, user_id: int, kind: str, allowance: int, now=None):
    name, period = _split(kind)
    key = period_key(period, now)
    row = (
        db.query(models_db.QuotaBucket)
        .filter_by(user_id=user_id, kind=name, period_key=key)
        .one_or_none()
    )
    if row is not None:
        return row
    row = models_db.QuotaBucket(
        user_id=user_id, kind=name, period_key=key, allowance=allowance, used=0
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # 并发开桶，别人先建成了。rollback 已经撤销我们这次 INSERT，
        # **不要做任何补偿写** —— billing.reserve 当年就是栽在这里
        # （见 tests/web_ui/test_billing_race.py）。
        db.rollback()
        row = (
            db.query(models_db.QuotaBucket)
            .filter_by(user_id=user_id, kind=name, period_key=key)
            .one()
        )
    return row


def peek(db: Session, user_id: int, kind: str, allowance: int, now=None) -> Tuple[int, int]:
    """返回 (已用, 限额)。限额取**桶上的快照**，不是传进来的当前套餐值。"""
    row = _ensure_bucket(db, user_id, kind, allowance, now)
    return int(row.used), int(row.allowance)


def try_consume(db: Session, user_id: int, kind: str, allowance: int, n: int = 1, now=None) -> bool:
    """原子消费 n 份额度。额度不足返回 False 且不改任何行。"""
    if n <= 0:
        raise ValueError("n 必须 >= 1")
    row = _ensure_bucket(db, user_id, kind, allowance, now)
    result = db.execute(
        text("UPDATE quota_buckets SET used = used + :n "
             "WHERE id = :bid AND used + :n <= allowance"),
        {"n": n, "bid": row.id},
    )
    db.commit()
    return result.rowcount == 1


def release(db: Session, user_id: int, kind_name: str, period_key_value: str, n: int = 1) -> bool:
    """把已消费的 n 份额度还回**指定周期**的桶。

    **必须传入当初消费时那个 period_key，不能在这里重算当前时间**：
    回收器可能在下一周才跑到一个上周崩掉的任务，重算会去减错桶——
    既没还上旧桶，又把新周别人的 used 减掉了。调用方从
    `ReportTask.free_grant_period` 取这个值（Task 5 已把它存在任务行上）。

    这是对**已提交行**的一次独立 UPDATE，不是「rollback 之后补偿」——
    后者正是 billing.reserve 当年的 bug（见 tests/web_ui/test_billing_race.py）。
    """
    result = db.execute(
        text("UPDATE quota_buckets SET used = used - :n "
             "WHERE user_id = :uid AND kind = :k AND period_key = :pk AND used >= :n"),
        {"n": n, "uid": user_id, "k": kind_name, "pk": period_key_value},
    )
    db.commit()
    return result.rowcount == 1
