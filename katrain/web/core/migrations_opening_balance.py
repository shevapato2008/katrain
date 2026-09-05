"""给存量余额补一条开账账本行。

背景：新账号的 credits 一直来自列默认值（10000），从不走账本。
开始扣费之前必须让「账本增量」能解释「当前余额」，否则事后审计、
补偿、回滚都无法区分历史默认赠额、管理员赠额与真实充值。

**这个迁移只补账、不改余额**：delta 就是用户当前的余额，balance_after 也是它。
选择 grandfather（保留存量余额）而不是清零 —— 清零会让老用户在毫无预告的
情况下损失既得，那是产品决策不是迁移能替 Fan 做的。
"""
import logging

from sqlalchemy.orm import Session

from katrain.web.core import models_db

logger = logging.getLogger("katrain_web")


def backfill_opening_balances(db: Session, batch: int = 500) -> int:
    """给每个存量用户补一条**残差**开账行，直到全部处理完。返回补的条数。

    **为什么不是「跳过已有账本的用户」**：那个写法漏掉最典型的一类人——
    从列默认值拿了 10000、又兑换过 500 的用户，余额 10500 而账本只有 +500。
    他有账本行，于是被跳过，那 10000 永远无法被账本解释。
    正确的判据是**残差**：`residual = credits - sum(有效账本 delta)`，
    残差非 0 就补一行。残差为 0 的用户天然跳过，不需要额外条件。

    有效 delta = status in ('committed', 'reserved')。`reserved` 也算，因为它
    已经从 users.credits 里扣掉了（见 billing.reserve 的条件 UPDATE）。

    **这个迁移只补账、不改余额**：选 grandfather（保留存量余额）而不是清零——
    清零会让老用户在毫无预告的情况下损失既得，那是产品决策，迁移替不了 Fan 做。
    """
    from sqlalchemy import func as sa_func

    ledger = (
        db.query(
            models_db.CreditTransaction.user_id.label("uid"),
            sa_func.coalesce(sa_func.sum(models_db.CreditTransaction.delta), 0).label("total"),
        )
        .filter(models_db.CreditTransaction.status.in_(("committed", "reserved")))
        .group_by(models_db.CreditTransaction.user_id)
        .subquery()
    )
    rows = (
        db.query(models_db.User, sa_func.coalesce(ledger.c.total, 0))
        .outerjoin(ledger, ledger.c.uid == models_db.User.id)
        .filter(models_db.User.credits != sa_func.coalesce(ledger.c.total, 0))
        .limit(batch)
        .all()
    )
    n = 0
    for u, ledger_total in rows:
        residual = int(u.credits) - int(ledger_total)
        if residual == 0:
            continue
        ref = f"opening_balance:{u.id}"
        if db.query(models_db.CreditTransaction).filter_by(ref_id=ref).first() is not None:
            # 已经补过一次却仍有残差 —— 说明账本之外还有别的写入路径，报警别静默。
            logger.error("用户 %s 已有 opening_balance 行但残差仍为 %s", u.id, residual)
            continue
        db.add(
            models_db.CreditTransaction(
                user_id=u.id,
                delta=residual,
                reason="opening_balance",
                ref_id=ref,
                status="committed",
                balance_after=int(u.credits),
            )
        )
        n += 1
    if n:
        db.commit()
        logger.info("opening_balance: 补了 %s 条开账行", n)
    return n


def count_users_needing_opening_balance(db: Session) -> int:
    """还有多少用户的余额与「有效账本增量」对不上。收敛判据用它，不用「写了几条」。"""
    from sqlalchemy import func as sa_func

    ledger = (
        db.query(
            models_db.CreditTransaction.user_id.label("uid"),
            sa_func.coalesce(sa_func.sum(models_db.CreditTransaction.delta), 0).label("total"),
        )
        .filter(models_db.CreditTransaction.status.in_(("committed", "reserved")))
        .group_by(models_db.CreditTransaction.user_id)
        .subquery()
    )
    return (
        db.query(models_db.User)
        .outerjoin(ledger, ledger.c.uid == models_db.User.id)
        .filter(models_db.User.credits != sa_func.coalesce(ledger.c.total, 0))
        .count()
    )


def backfill_all_opening_balances(db: Session, batch: int = 500, max_rounds: int = 200) -> int:
    """循环调用直到没有可补的为止。启动时只调一次 backfill_opening_balances
    会把 batch 之外的用户永久留在不一致状态。"""
    total = 0
    for _ in range(max_rounds):
        pending = count_users_needing_opening_balance(db)
        if pending == 0:
            return total                      # 真收敛：没有残差非 0 的用户了
        written = backfill_opening_balances(db, batch)
        total += written
        if written == 0:
            # 还有残差非 0 的行，却一条都没能补上 —— 全落进了「已有 opening_balance
            # 行却仍有残差」那个报警分支。继续循环只会把同一批行反复取出来，
            # 停下并报警，**不要假装迁移完成**：那正是最不该静默的时候。
            logger.error(
                "opening_balance: 还有 %s 个用户残差非 0 但一条都没能补账。"
                "迁移未完成，开闸前必须人工核查。",
                pending,
            )
            return total
    logger.error("opening_balance: 达到 max_rounds 仍未收敛，剩余用户未迁移")
    return total
