"""Phase 2: server-authoritative integer credit ledger.

Covers atomic spend, reserve/commit/refund lifecycle, idempotency on ref_id,
exact-balance boundaries, redeem (valid/used/expired/concurrent), order settle,
and stale-reservation reconcile. Uses an isolated in-memory SQLite DB.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import billing, models_db


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _mkuser(db, credits=100, username="u1", is_admin=False):
    u = models_db.User(username=username, hashed_password="x", credits=credits, is_admin=is_admin)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# --- balance + spend ----------------------------------------------------------


def test_spend_debits_and_records_ledger(db):
    u = _mkuser(db, credits=100)
    bal = billing.spend(db, u.id, 30, "analysis_territory", ref_id="r1")
    assert bal == 70
    assert billing.get_balance(db, u.id) == 70
    tx = db.query(models_db.CreditTransaction).filter_by(ref_id="r1").one()
    assert tx.delta == -30 and tx.status == "committed" and tx.balance_after == 70


def test_spend_insufficient_raises_and_does_not_debit(db):
    u = _mkuser(db, credits=10)
    with pytest.raises(billing.InsufficientCredits):
        billing.spend(db, u.id, 30, "analysis_territory", ref_id="r1")
    assert billing.get_balance(db, u.id) == 10
    assert db.query(models_db.CreditTransaction).count() == 0


def test_spend_exact_balance_succeeds_then_next_fails(db):
    u = _mkuser(db, credits=30)
    assert billing.spend(db, u.id, 30, "k", ref_id="r1") == 0
    with pytest.raises(billing.InsufficientCredits):
        billing.spend(db, u.id, 1, "k", ref_id="r2")
    assert billing.get_balance(db, u.id) == 0


def test_spend_idempotent_same_ref_id_charges_once(db):
    u = _mkuser(db, credits=100)
    b1 = billing.spend(db, u.id, 30, "k", ref_id="same")
    b2 = billing.spend(db, u.id, 30, "k", ref_id="same")
    assert b1 == b2 == 70
    assert billing.get_balance(db, u.id) == 70
    assert db.query(models_db.CreditTransaction).filter_by(ref_id="same").count() == 1


# --- reserve / commit / refund ------------------------------------------------


def test_reserve_then_commit(db):
    u = _mkuser(db, credits=100)
    assert billing.reserve(db, u.id, 40, "analysis_hints", ref_id="x") == 60
    assert billing.get_balance(db, u.id) == 60
    assert billing.commit(db, "x") == 60
    tx = db.query(models_db.CreditTransaction).filter_by(ref_id="x").one()
    assert tx.status == "committed"


def test_reserve_then_refund_restores_balance(db):
    u = _mkuser(db, credits=100)
    billing.reserve(db, u.id, 40, "analysis_hints", ref_id="x")
    assert billing.get_balance(db, u.id) == 60
    assert billing.refund(db, "x") == 100
    tx = db.query(models_db.CreditTransaction).filter_by(ref_id="x").one()
    assert tx.status == "refunded"
    # audit row recorded
    assert db.query(models_db.CreditTransaction).filter_by(ref_id="refund:x").count() == 1


def test_refund_is_idempotent(db):
    u = _mkuser(db, credits=100)
    billing.reserve(db, u.id, 40, "k", ref_id="x")
    billing.refund(db, "x")
    billing.refund(db, "x")  # second refund must be a no-op
    assert billing.get_balance(db, u.id) == 100


def test_commit_then_refund_is_noop(db):
    u = _mkuser(db, credits=100)
    billing.reserve(db, u.id, 40, "k", ref_id="x")
    billing.commit(db, "x")
    billing.refund(db, "x")  # committed spends are not reversible via refund
    assert billing.get_balance(db, u.id) == 60


# --- grant --------------------------------------------------------------------


def test_grant_credits_and_idempotent(db):
    u = _mkuser(db, credits=10)
    assert billing.grant(db, u.id, 500, "admin_grant", ref_id="g1") == 510
    assert billing.grant(db, u.id, 500, "admin_grant", ref_id="g1") == 510  # idempotent
    assert billing.get_balance(db, u.id) == 510


# --- redeem -------------------------------------------------------------------


def test_redeem_valid_code(db):
    u = _mkuser(db, credits=0)
    (code,) = billing.generate_redeem_codes(db, count=1, credits=250)
    assert billing.redeem(db, u.id, code) == 250
    rc = db.query(models_db.RedeemCode).filter_by(code=code).one()
    assert rc.used_by == u.id and rc.used_at is not None


def test_redeem_used_code_fails(db):
    u = _mkuser(db, credits=0)
    u2 = _mkuser(db, credits=0, username="u2")
    (code,) = billing.generate_redeem_codes(db, count=1, credits=250)
    billing.redeem(db, u.id, code)
    with pytest.raises(billing.InvalidRedeemCode):
        billing.redeem(db, u2.id, code)
    assert billing.get_balance(db, u2.id) == 0


def test_redeem_invalid_code_fails(db):
    u = _mkuser(db, credits=0)
    with pytest.raises(billing.InvalidRedeemCode):
        billing.redeem(db, u.id, "deadbeef")


def test_redeem_expired_code_fails(db):
    u = _mkuser(db, credits=0)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    (code,) = billing.generate_redeem_codes(db, count=1, credits=250, expires_at=past)
    with pytest.raises(billing.InvalidRedeemCode):
        billing.redeem(db, u.id, code)
    assert billing.get_balance(db, u.id) == 0


def test_redeem_codes_are_high_entropy(db):
    codes = billing.generate_redeem_codes(db, count=5, credits=10)
    assert all(len(c) == 32 for c in codes)  # 16 bytes hex = 128 bit
    assert len(set(codes)) == 5


# --- order settle -------------------------------------------------------------


def test_settle_order_grants_and_idempotent(db):
    u = _mkuser(db, credits=0)
    order = models_db.RechargeOrder(
        out_trade_no="ot1", user_id=u.id, package_id="p1", amount_fen=1000, credits=1200, provider="manual"
    )
    db.add(order)
    db.commit()
    assert billing.settle_order(db, "ot1") == 1200
    assert billing.settle_order(db, "ot1") == 1200  # idempotent, no double grant
    assert billing.get_balance(db, u.id) == 1200
    assert db.query(models_db.RechargeOrder).filter_by(out_trade_no="ot1").one().status == "paid"


# --- reconcile ----------------------------------------------------------------


def test_reconcile_refunds_stale_reservations(db):
    u = _mkuser(db, credits=100)
    billing.reserve(db, u.id, 40, "analysis_hints", ref_id="stale")
    # backdate the reservation to look stale
    tx = db.query(models_db.CreditTransaction).filter_by(ref_id="stale").one()
    tx.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()

    n = billing.reconcile_stale_reservations(db, ttl_seconds=60)
    assert n == 1
    assert billing.get_balance(db, u.id) == 100
    assert db.query(models_db.CreditTransaction).filter_by(ref_id="stale").one().status == "refunded"


def test_reconcile_leaves_fresh_reservations(db):
    u = _mkuser(db, credits=100)
    billing.reserve(db, u.id, 40, "k", ref_id="fresh")
    n = billing.reconcile_stale_reservations(db, ttl_seconds=3600)
    assert n == 0
    assert billing.get_balance(db, u.id) == 60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
