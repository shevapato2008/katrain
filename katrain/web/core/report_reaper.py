"""复盘预扣的兜底回收。

Task 6 把 reason="report" 排除出通用 TTL 回收器之后，复盘预扣就**只剩
结算器一个管理者**，而结算器按 ReportTask 行遍历。这里收两类它够不着的钱：
任务行已经没了的孤儿预扣，和卡在 authorizing 的半成品。
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from katrain.web.core import billing, models_db, quota

logger = logging.getLogger("katrain_web")


def reap_orphaned_report_charges(db: Session, limit: int = 200) -> int:
    """退还「任务行已经不存在」的复盘预扣。

    UserGame 对 ReportTask 是 cascade delete-orphan，删棋谱会带走任务行，
    预扣却留在账本里 —— 没有这个回收器，那笔钱永久冻结。
    """
    rows = (
        db.query(models_db.CreditTransaction)
        .filter(
            models_db.CreditTransaction.status == "reserved",
            models_db.CreditTransaction.reason == "report",
        )
        .limit(limit)
        .all()
    )
    n = 0
    for tx in rows:
        # ref 有两种形状：建任务时的 `report:{id}`，与 /retry 重新授权时的
        # `report:{id}:retryN`（Task 6 引入）。用 split(":", 1) 取第二段会拿到
        # "5:retry1" 而 int() 抛异常被跳过 —— 那样重试产生的孤儿预扣永远收不回来。
        parts = tx.ref_id.split(":")
        try:
            task_id = int(parts[1])
        except (IndexError, ValueError):
            logger.warning("无法从 ref_id %s 解析任务号，跳过", tx.ref_id)
            continue
        if db.query(models_db.ReportTask.id).filter_by(id=task_id).first() is not None:
            continue
        billing.refund(db, tx.ref_id)
        logger.info("退还孤儿复盘预扣 %s", tx.ref_id)
        n += 1
    return n


def reap_stale_authorizing(db: Session, ttl_sec: int = 600, limit: int = 200) -> int:
    """回滚卡在 authorizing 的任务：退积分、还额度、删任务行。

    cron 只认 pending，结算器只看终态 —— 这个状态没有别的管理者。
    ttl 要明显大于一次正常授权耗时（默认 600 秒），免得抢走正在进行的请求
    （见 test_fresh_authorizing_task_is_left_alone）。

    **不能只信 `t.charge_ref` 这一列**：建任务路径是「先落意图、再动钱」
    （见 reports.py:create_report_task 的注释），存在 charge_ref 已写但预扣
    尚未落盘、或 charge_ref 列本身没同步上的中间态。这里额外按
    `f"report:{t.id}"` 直接推导 ref 去查账本，两条线都查过才退款，
    不相信列值一定和账本一致。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=ttl_sec)
    tasks = (
        db.query(models_db.ReportTask)
        .filter(
            models_db.ReportTask.status == "authorizing",
            models_db.ReportTask.created_at < cutoff,
        )
        .limit(limit)
        .all()
    )
    n = 0
    for t in tasks:
        derived_ref = f"report:{t.id}"
        for ref in {r for r in (t.charge_ref, derived_ref) if r}:
            if billing.transaction_status(db, ref) == "reserved":
                billing.refund(db, ref)
        if t.free_grant_period:
            # 按**任务上存着的**那个周期键还，不是当前周（见 quota.release 的注释）。
            #
            # ⚠️ free_grant_period 是**意图位**不是消费凭证：建任务路径先写它并 commit、
            # 再调 quota.try_consume（"先落意图、再动钱"）。两句之间出错时桶里可能
            # 根本没有这份消费，而 release 的 `used >= n` 守卫只保证不减成负数、
            # **挡不住"减掉别人那一份"** —— 同一周内别的任务消费过就会被误减，
            # 用户白得一次免费复盘。
            # 所以还完立刻把意图位清掉：这一步幂等，重复回收不会二次释放。
            released = quota.release(db, t.user_id, "free_report", t.free_grant_period)
            t.free_grant_period = None
            if not released:
                logger.info("复盘 %s 的免费额度无需释放（桶里没有这份消费）", t.id)
        db.delete(t)
        db.commit()
        logger.info("回滚滞留的 authorizing 任务 %s", t.id)
        n += 1
    return n
