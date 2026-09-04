"""Server-authoritative single-pool credit ledger.

All amounts are integers. The User.credits column is the live balance; every
balance change also appends a CreditTransaction row keyed by a unique, idempotent
`ref_id`. Spends use a reserve -> commit | refund lifecycle so a crash between
"charge" and "deliver" can be reconciled instead of silently eating credits.

This module is the LOCAL (server-authoritative) implementation. In board (kiosk)
mode these operations are proxied to the cloud instead (see billing_proxy.py);
the kiosk never spends against its local SQLite.

Concurrency model
-----------------
- spend/reserve: a single conditional UPDATE
      UPDATE users SET credits = credits - :amt WHERE id = :uid AND credits >= :amt
  whose rowcount tells us atomically whether the balance was sufficient. No
  read-modify-write race, works on both SQLite and Postgres.
- redeem: a single conditional UPDATE claims the code (WHERE used_by IS NULL ...),
  rowcount decides the winner under concurrency.
- idempotency: ref_id has a UNIQUE constraint; inserting a duplicate raises
  IntegrityError which we map to "already processed -> return existing".
"""

import logging
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from katrain.web.core import models_db

logger = logging.getLogger("katrain_web")


class BillingError(Exception):
    """Base class for billing errors."""


class InsufficientCredits(BillingError):
    pass


class InvalidRedeemCode(BillingError):
    pass


class NeedOnline(BillingError):
    """Raised in board mode when the cloud billing backend is unreachable."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_balance(db: Session, user_id: int) -> int:
    row = db.query(models_db.User.credits).filter(models_db.User.id == user_id).first()
    if row is None:
        raise BillingError(f"user {user_id} not found")
    return int(row[0] or 0)


def _existing_tx(db: Session, ref_id: str) -> Optional[models_db.CreditTransaction]:
    return db.query(models_db.CreditTransaction).filter(models_db.CreditTransaction.ref_id == ref_id).one_or_none()


def reserve(db: Session, user_id: int, amount: int, reason: str, ref_id: str) -> int:
    """Atomically reserve (debit) `amount` credits, writing a status='reserved' row.

    Idempotent on ref_id: replaying returns the already-recorded balance_after and
    does not debit again. Raises InsufficientCredits if the balance is too low.
    Returns the balance after the reservation.
    """
    if amount < 0:
        raise BillingError("reserve amount must be >= 0")

    existing = _existing_tx(db, ref_id)
    if existing is not None:
        return int(existing.balance_after)

    # Atomic conditional debit — rowcount==0 means insufficient funds.
    result = db.execute(
        text("UPDATE users SET credits = credits - :amt WHERE id = :uid AND credits >= :amt"),
        {"amt": amount, "uid": user_id},
    )
    if result.rowcount == 0:
        db.rollback()
        # Distinguish "no such user" from "insufficient".
        if db.query(models_db.User.id).filter(models_db.User.id == user_id).first() is None:
            raise BillingError(f"user {user_id} not found")
        raise InsufficientCredits(f"user {user_id} has insufficient credits for {amount}")

    balance_after = get_balance(db, user_id)
    tx = models_db.CreditTransaction(
        user_id=user_id,
        delta=-amount,
        reason=reason,
        ref_id=ref_id,
        status="reserved",
        balance_after=balance_after,
    )
    db.add(tx)
    try:
        db.commit()
    except IntegrityError:
        # Lost an idempotency race: another request inserted the same ref_id.
        # db.rollback() already undoes our debit within this transaction —
        # do NOT re-credit here, that would double-undo and gift `amount` for free.
        db.rollback()
        winner = _existing_tx(db, ref_id)
        return int(winner.balance_after) if winner else get_balance(db, user_id)
    return balance_after


def commit(db: Session, ref_id: str) -> int:
    """Finalize a reservation (reserved -> committed). Idempotent. Returns balance."""
    tx = _existing_tx(db, ref_id)
    if tx is None:
        raise BillingError(f"no transaction for ref_id {ref_id}")
    if tx.status == "reserved":
        tx.status = "committed"
        tx.updated_at = _now()
        db.commit()
    return get_balance(db, tx.user_id)


def refund(db: Session, ref_id: str) -> int:
    """Reverse a reservation (reserved -> refunded), re-crediting the user. Idempotent."""
    tx = _existing_tx(db, ref_id)
    if tx is None:
        raise BillingError(f"no transaction for ref_id {ref_id}")
    if tx.status != "reserved":
        # Already committed or already refunded — no-op (idempotent).
        return get_balance(db, tx.user_id)

    amount = -tx.delta  # delta is negative for a spend
    db.execute(
        text("UPDATE users SET credits = credits + :amt WHERE id = :uid"),
        {"amt": amount, "uid": tx.user_id},
    )
    tx.status = "refunded"
    tx.updated_at = _now()
    balance_after = get_balance(db, tx.user_id)
    # Record the reversal as a separate committed ledger row for auditability.
    db.add(
        models_db.CreditTransaction(
            user_id=tx.user_id,
            delta=amount,
            reason=f"refund:{tx.reason}",
            ref_id=f"refund:{ref_id}",
            status="committed",
            balance_after=balance_after,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # refund row already exists (replayed) — balance already correct
    return get_balance(db, tx.user_id)


def grant(db: Session, user_id: int, amount: int, reason: str, ref_id: str) -> int:
    """Atomically credit `amount`, writing a committed ledger row. Idempotent on ref_id."""
    if amount < 0:
        raise BillingError("grant amount must be >= 0")

    existing = _existing_tx(db, ref_id)
    if existing is not None:
        return int(existing.balance_after)

    db.execute(
        text("UPDATE users SET credits = credits + :amt WHERE id = :uid"),
        {"amt": amount, "uid": user_id},
    )
    balance_after = get_balance(db, user_id)
    db.add(
        models_db.CreditTransaction(
            user_id=user_id,
            delta=amount,
            reason=reason,
            ref_id=ref_id,
            status="committed",
            balance_after=balance_after,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        # Idempotency race — db.rollback() already undoes our credit within this
        # transaction. Do NOT debit again here, that would double-undo and dock
        # the user for a grant they never received.
        db.rollback()
        winner = _existing_tx(db, ref_id)
        return int(winner.balance_after) if winner else get_balance(db, user_id)
    return balance_after


def spend(db: Session, user_id: int, amount: int, reason: str, ref_id: str) -> int:
    """Convenience: reserve + immediately commit. For one-shot non-reversible charges."""
    balance = reserve(db, user_id, amount, reason, ref_id)
    commit(db, ref_id)
    return balance


def generate_redeem_codes(db: Session, count: int, credits: int, expires_at: Optional[datetime] = None) -> List[str]:
    """Create `count` high-entropy single-use codes worth `credits` each."""
    if count < 1 or credits < 1:
        raise BillingError("count and credits must be >= 1")
    codes = []
    for _ in range(count):
        code = secrets.token_hex(16)  # 128-bit, not enumerable
        db.add(models_db.RedeemCode(code=code, credits=credits, expires_at=expires_at))
        codes.append(code)
    db.commit()
    return codes


def redeem(db: Session, user_id: int, code: str) -> int:
    """Claim a redeem code atomically and grant its credits. Returns new balance.

    Uses a single conditional UPDATE so concurrent redemptions of the same code
    cannot double-grant. Errors are intentionally indistinguishable (invalid /
    used / expired all raise InvalidRedeemCode) to avoid leaking code validity.
    """
    now = _now()
    result = db.execute(
        text(
            "UPDATE redeem_codes SET used_by = :uid, used_at = :now "
            "WHERE code = :code AND used_by IS NULL "
            "AND (expires_at IS NULL OR expires_at > :now)"
        ),
        {"uid": user_id, "now": now, "code": code},
    )
    if result.rowcount != 1:
        db.rollback()
        raise InvalidRedeemCode("invalid, used, or expired code")

    row = db.execute(text("SELECT credits FROM redeem_codes WHERE code = :code"), {"code": code}).first()
    credits = int(row[0])
    db.commit()
    # ref_id ties the grant to the code so a retry can't double-grant.
    return grant(db, user_id, credits, reason="redeem", ref_id=f"redeem:{code}")


def settle_order(db: Session, out_trade_no: str) -> int:
    """Mark a recharge order paid and grant its credits. Idempotent on the order.

    Returns the user's new balance. Confirming an already-paid order is a no-op.
    """
    order = db.query(models_db.RechargeOrder).filter(models_db.RechargeOrder.out_trade_no == out_trade_no).one_or_none()
    if order is None:
        raise BillingError(f"order {out_trade_no} not found")
    if order.status == "paid":
        return get_balance(db, order.user_id)
    if order.status == "cancelled":
        raise BillingError(f"order {out_trade_no} is cancelled")

    order.status = "paid"
    order.settled_at = _now()
    db.commit()
    return grant(db, order.user_id, int(order.credits), reason="order", ref_id=f"order:{out_trade_no}")


# 这些 reason 的预扣有自己的生命周期管理者，通用 TTL 回收器一律不碰。
# 复盘要跑几分钟到几十分钟，远超 BILLING_RESERVATION_TTL_SEC(120)；
# 让通用回收器碰它 = 每次 web 重启把在跑的复盘全额退掉，之后结算再对一个
# 已 refunded 的行 commit（无效）并补一笔"估多退款" —— 白嫖 + 凭空生钱。
# 复盘预扣改由 report_settlement.settle_finished_reports 按任务终态回收。
LONG_RUNNING_REASONS = frozenset({"report"})


def reconcile_stale_reservations(db: Session, ttl_seconds: int) -> int:
    """Refund reservations older than ttl_seconds still stuck in 'reserved'.

    Called at startup to recover credits from spends whose deliver step never
    committed (crash/timeout). Returns the number of reservations refunded.

    Reservations whose `reason` is in LONG_RUNNING_REASONS are excluded: those
    have their own terminal-state-driven reconciler and can legitimately stay
    'reserved' far longer than ttl_seconds.
    """
    from datetime import timedelta

    cutoff = _now() - timedelta(seconds=ttl_seconds)
    stale = (
        db.query(models_db.CreditTransaction)
        .filter(
            models_db.CreditTransaction.status == "reserved",
            models_db.CreditTransaction.created_at < cutoff,
            ~models_db.CreditTransaction.reason.in_(LONG_RUNNING_REASONS),
        )
        .all()
    )
    n = 0
    for tx in stale:
        try:
            refund(db, tx.ref_id)
            n += 1
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"reconcile: failed to refund {tx.ref_id}: {e}")
    if n:
        logger.info(f"reconcile: refunded {n} stale reservation(s)")
    return n


def reserved_amount(db: Session, ref_id: str) -> int:
    """某笔预扣的金额（正数）。找不到抛 BillingError。"""
    tx = _existing_tx(db, ref_id)
    if tx is None:
        raise BillingError(f"no transaction for ref_id {ref_id}")
    return abs(int(tx.delta))


def has_transaction(db: Session, ref_id: str) -> bool:
    return _existing_tx(db, ref_id) is not None


def transaction_status(db: Session, ref_id: str) -> Optional[str]:
    tx = _existing_tx(db, ref_id)
    return None if tx is None else str(tx.status)
