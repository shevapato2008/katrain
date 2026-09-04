"""终态复盘任务的对账结算。

**为什么是对账不是让 worker 结算**：跑复盘的是 `katrain/cron/jobs/report_analyze.py`，
而 `Dockerfile.cron` 只 `COPY katrain/cron/`、该子树只 import `katrain.cron.*`。
从那里 import `katrain.web.core.billing` 本机能跑、**容器里必炸**。

**时延语义（诚实性）**：从任务终态到余额准确之间有一个对账周期的窗口。
所以 `/billing/quota` 必须在返回余额前先跑一次本用户的结算（见 Task 11），
用户看到的数才是准的；后台周期跑只是兜底。
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from katrain.web.core import analysis_cost, billing, models_db

logger = logging.getLogger("katrain_web")

# 只有 completed 是「可以立刻结算」的终态。
# failed 不在这里 —— 它可能被 /retry 复活，立刻终结授权会让用户免费续跑
# （见 reports.py:/retry 与 REPORT_RETRY_GRACE_SEC）。failed 走下面 grace_cutoff 分支。
TERMINAL_STATUSES = ("completed",)


def settle_finished_reports(db: Session, limit: int = 200, user_id: int | None = None) -> int:
    """结算终态但仍持预扣的复盘任务。返回结算条数。幂等。"""
    from sqlalchemy import or_
    from katrain.web.core.config import settings

    grace_cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=settings.REPORT_RETRY_GRACE_SEC
    )
    # 注意这里**没有**过滤 `billing_exempt_reason`。
    # 曾经有过 `billing_exempt_reason.is_(None)` 这个条件，那是个漏钱的写法：
    # 运维 requeue 一个还持着 reserved 预扣的任务之后，它会被结算器永久跳过，
    # 而 reason="report" 的预扣又被排除在通用 TTL 回收器之外
    # （见 billing.LONG_RUNNING_REASONS）⇒ 那笔积分冻结在账本里，
    # 没有任何管理者够得着。
    # 现在 exempt 只决定**怎么结**（见下方全额退那一支），不决定**结不结**。
    q = db.query(models_db.ReportTask).filter(
        models_db.ReportTask.charge_ref.isnot(None),
        or_(
            models_db.ReportTask.status.in_(TERMINAL_STATUSES),
            # failed 过了宽限期才结算：宽限期内 /retry 可以复用原预扣。
            (models_db.ReportTask.status == "failed")
            & (models_db.ReportTask.updated_at < grace_cutoff),
            # 运维重排掉的任务不论当前状态都要把挂着的预扣清掉（全额退，见下）。
            models_db.ReportTask.billing_exempt_reason.isnot(None),
        ),
    )
    if user_id is not None:
        q = q.filter(models_db.ReportTask.user_id == user_id)

    settled = 0
    for task in q.limit(limit).all():
        ref = task.charge_ref
        status = billing.transaction_status(db, ref)

        if task.billing_exempt_reason is not None:
            # 运维重排：结果被删掉重跑，用户不该为一份已经不存在的报告付钱。
            # 全额退，而不是按 analyzed_moves 结算 —— 那份分析的产出已经没了。
            if status == "reserved":
                billing.refund(db, ref)
                logger.info(
                    "运维重排的复盘 %s 全额退还预扣（%s）", task.id, task.billing_exempt_reason
                )
            task.charge_ref = None
            db.commit()
            settled += 1
            continue

        if status == "refunded":
            # 已被别处退掉。原地摘掉引用，**不要**再动余额 ——
            # 在一个已退款的预扣上补"估多退款"就是凭空生钱。
            logger.warning("复盘 %s 的预扣已是 refunded，跳过结算", task.id)
            task.charge_ref = None
            db.commit()
            continue
        if status == "committed":
            # 上一轮在 commit 与 grant 之间崩了 —— 预扣已落定，差额还没退。
            # 退款行的 ref_id 是确定性的，据此判断该补不该补。
            # （不加这一段，用户会被永久按完整预估收费。）
            reserved = billing.reserved_amount(db, ref)
            actual = analysis_cost.report_cost(task.analyzed_moves or 0, task.requested_visits or 0)
            if reserved > actual and not billing.has_transaction(db, f"{ref}:refund"):
                billing.grant(db, task.user_id, reserved - actual,
                              reason="report_overestimate_refund", ref_id=f"{ref}:refund")
                logger.info("补退复盘 %s 的估算差额 %s", task.id, reserved - actual)
            task.charge_ref = None
            db.commit()
            settled += 1
            continue
        if status != "reserved":
            logger.warning("复盘 %s 的预扣状态是 %s，跳过", task.id, status)
            task.charge_ref = None
            db.commit()
            continue

        actual = analysis_cost.report_cost(task.analyzed_moves or 0, task.requested_visits or 0)
        try:
            if actual <= 0:
                billing.refund(db, ref)
            else:
                reserved = billing.reserved_amount(db, ref)
                billing.commit(db, ref)
                if reserved > actual:
                    billing.grant(db, task.user_id, reserved - actual,
                                  reason="report_overestimate_refund", ref_id=f"{ref}:refund")
                # reserved < actual 在本设计里不可能：Task 4 让 total_moves 成为契约、
                # cron 只分析已付费前缀，所以 analyzed_moves <= total_moves。
                # 真出现了说明那条不变式破了 —— 报警，不要静默吞掉。
                elif reserved < actual:
                    logger.error(
                        "复盘 %s 实际成本 %s 超过预扣 %s —— total_moves 契约被破坏了",
                        task.id, actual, reserved,
                    )
            task.charge_ref = None
            db.commit()
            settled += 1
        except billing.BillingError:
            logger.exception("结算复盘任务 %s 失败，留待下一轮", task.id)
            db.rollback()
    return settled
