"""Real PostgreSQL order atomicity and immutable server snapshots."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker

from tests.web_ui.membership_test_support import membership_pg_engine
from katrain.web.core import models_db as m

NOW = datetime(2026, 11, 2, 3, tzinfo=timezone.utc)


@pytest.fixture
def cfg(monkeypatch):
    import os

    monkeypatch.setenv("KATRAIN_DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    return SimpleNamespace(
        KATRAIN_ENVIRONMENT="test",
        PAYMENTS_MODE="mock",
        MEMBERSHIP_MODE="enabled",
        BILLING_ENFORCED=True,
        PAYMENT_MOCK_EVENT_SECRET="test-event-signing-key",
        MEMBERSHIP_MAX_SALE_ENABLED=True,
    )


def services():
    from katrain.web.core import payments, payment_mock

    return payments, payment_mock


def seed(engine, name="buyer", credits=0):
    Session = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        user = m.User(username=name, hashed_password="x", credits=credits)
        db.add(user)
        db.flush()
        return user.id


def create(db, uid, cfg, *, sku="topup_10", key="buy"):
    pay, _ = services()
    return pay.create_order_in_transaction(
        db, user_id=uid, sku=sku, provider="mock", idempotency_key=key, now=NOW, settings=cfg
    )


def event(order, uid, *, tx="provider-1", status="paid"):
    return {
        "order_id": str(order.id),
        "owner_id": uid,
        "environment": "test",
        "amount_fen": order.amount_fen,
        "provider_tx_id": tx,
        "status": status,
    }


def deliver(db, payload, cfg, *, now=NOW):
    pay, _ = services()
    return pay.apply_provider_event_in_transaction(db, event=payload, now=now, settings=cfg)


@pytest.mark.parametrize("sku", ["topup_10", "membership_max"])
def test_create_snapshot_replay_and_conflict(membership_pg_engine, cfg, sku):
    pay, _ = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        order = create(db, uid, cfg, sku=sku)
        if sku == "membership_max":
            assert order.amount_fen == 19900 and order.credits == 0
            assert order.sku_snapshot == {
                "sku": "membership_max",
                "kind": "membership",
                "plan_code": "max",
                "amount_fen": 19900,
                "credits": 0,
                "term_days": 30,
                "term_units": 72240,
                "week_units": 24080,
            }
        else:
            assert order.amount_fen == 1000 and order.credits == 1000
            assert order.sku_snapshot["sku"] == "topup_10"
        assert order.expires_at == NOW + timedelta(minutes=15)
        assert create(db, uid, cfg, sku=sku).id == order.id
        with pytest.raises(pay.PaymentError, match="idempotency_conflict"):
            create(db, uid, cfg, sku="topup_30")
    with Session() as db:
        assert db.query(m.RechargeOrder).count() == 1
        assert db.get(m.User, uid).credits == 0


@pytest.mark.parametrize("sku", ["topup_10", "membership_max"])
def test_duplicate_paid_events_grant_exactly_once_and_ignore_late_failure(membership_pg_engine, cfg, sku):
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        order = create(db, uid, cfg, sku=sku)
        payload = event(order, uid)
    barrier = Barrier(2)

    def finish(_):
        with Session.begin() as db:
            barrier.wait()
            return deliver(db, payload, cfg).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(finish, range(2))) == ["paid", "paid"]
    with Session.begin() as db:
        deliver(db, {**payload, "status": "failed"}, cfg)
    with Session() as db:
        if sku == "membership_max":
            term = db.query(m.MembershipTerm).one()
            assert term.plan_id == "max" and term.limit == 72240
            assert term.ends_at - term.starts_at == timedelta(days=30)
            assert db.get(m.User, uid).credits == 0
            assert db.query(m.CreditTransaction).count() == 0
        else:
            assert db.get(m.User, uid).credits == 1000
            assert db.query(m.CreditTransaction).count() == 1
        assert db.query(m.RechargeOrder).one().status == "paid"


def test_simultaneous_membership_payments_have_nonoverlapping_terms(membership_pg_engine, cfg):
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        orders = [create(db, uid, cfg, sku="membership_plus", key=f"member-{i}") for i in range(2)]
        payloads = [event(o, uid, tx=f"term-{i}") for i, o in enumerate(orders)]
    barrier = Barrier(2)

    def finish(index):
        with Session.begin() as db:
            barrier.wait()
            deliver(db, payloads[index], cfg)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(finish, range(2)))
    with Session() as db:
        terms = db.query(m.MembershipTerm).order_by(m.MembershipTerm.starts_at).all()
        assert len(terms) == 2 and terms[0].ends_at == terms[1].starts_at
        assert db.get(m.User, uid).credits == 0


@pytest.mark.parametrize("changed", [{"owner_id": 999}, {"environment": "production"}, {"amount_fen": 1}])
def test_provider_event_binding_rejects_tampering(membership_pg_engine, cfg, changed):
    pay, _ = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        order = create(db, uid, cfg)
        payload = event(order, uid)
    with Session.begin() as db:
        with pytest.raises(pay.PaymentError):
            deliver(db, {**payload, **changed}, cfg)
    with Session() as db:
        assert db.get(m.User, uid).credits == 0
        assert db.query(m.RechargeOrder).one().status == "pending"


def test_payment_transaction_rolls_back_assets_and_order_together(membership_pg_engine, cfg):
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        order = create(db, uid, cfg)
        payload = event(order, uid)
    with pytest.raises(RuntimeError):
        with Session.begin() as db:
            deliver(db, payload, cfg)
            raise RuntimeError("downstream write failed")
    with Session() as db:
        assert db.get(m.User, uid).credits == 0
        assert db.query(m.CreditTransaction).count() == 0
        assert db.query(m.RechargeOrder).one().status == "pending"


def test_refund_replay_and_consumption_compete_under_user_lock(membership_pg_engine, cfg):
    pay, _ = services()
    from katrain.web.core import billing

    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        order = create(db, uid, cfg)
        deliver(db, event(order, uid), cfg)
        oid = order.id
    barrier = Barrier(2)

    def run(refund):
        with Session() as db:
            barrier.wait()
            try:
                if refund:
                    pay.refund_order_in_transaction(
                        db, user_id=uid, order_id=oid, refund_ref="full-refund", now=NOW, settings=cfg
                    )
                else:
                    db.query(m.User).filter_by(id=uid).with_for_update().one()
                    billing.apply_adjustment(db, uid, -1, "test_spend", "spend-1")
                db.commit()
                return "ok"
            except (pay.PaymentError, billing.InsufficientCredits):
                db.rollback()
                return "denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run, [True, False]))
    assert sorted(outcomes) == ["denied", "ok"]
    with Session() as db:
        receipt = db.get(m.RechargeOrder, oid)
        if receipt.status == "refunded":
            assert db.get(m.User, uid).credits == 0
            with Session.begin() as retry:
                pay.refund_order_in_transaction(
                    retry, user_id=uid, order_id=oid, refund_ref="full-refund", now=NOW, settings=cfg
                )
        else:
            assert receipt.status == "paid" and db.get(m.User, uid).credits == 999


def test_member_refund_denies_used_or_dependent_term(membership_pg_engine, cfg):
    pay, _ = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        first = create(db, uid, cfg, sku="membership_plus")
        deliver(db, event(first, uid), cfg)
        second = create(db, uid, cfg, sku="membership_pro", key="later")
        deliver(db, event(second, uid, tx="later-tx"), cfg)
        oid = first.id
    with Session.begin() as db:
        with pytest.raises(pay.PaymentError, match="manual_refund_required"):
            pay.refund_order_in_transaction(db, user_id=uid, order_id=oid, refund_ref="no-shift", now=NOW, settings=cfg)


def test_disabled_payment_mode_keeps_expired_receipt_readable(membership_pg_engine, cfg):
    pay, _ = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        oid = create(db, uid, cfg).id
    cfg.PAYMENTS_MODE = "disabled"
    with Session.begin() as db:
        order = pay.reconcile_order_in_transaction(
            db, user_id=uid, order_id=oid, now=NOW + timedelta(minutes=20), settings=cfg
        )
        receipt = pay.order_receipt(db, order, now=NOW + timedelta(minutes=20), payments_mode="disabled")
        assert receipt["status"] == "expired"


def test_unused_last_membership_can_be_refunded_once(membership_pg_engine, cfg):
    pay, _ = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        order = create(db, uid, cfg, sku="membership_plus")
        deliver(db, event(order, uid), cfg)
        pay.refund_order_in_transaction(
            db, user_id=uid, order_id=order.id, refund_ref="member-full", now=NOW, settings=cfg
        )
        pay.refund_order_in_transaction(
            db, user_id=uid, order_id=order.id, refund_ref="member-full", now=NOW, settings=cfg
        )
    with Session() as db:
        assert db.query(m.MembershipTerm).one().status == "refunded"
        assert db.query(m.RechargeOrder).one().status == "refunded"
        assert db.get(m.User, uid).credits == 0


@pytest.mark.parametrize("counter", ["used", "reserved"])
def test_member_refund_requires_no_consumed_or_reserved_units(membership_pg_engine, cfg, counter):
    pay, _ = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        order = create(db, uid, cfg, sku="membership_plus")
        deliver(db, event(order, uid), cfg)
        setattr(db.query(m.MembershipTerm).one(), counter, 1)
        oid = order.id
    with Session.begin() as db:
        with pytest.raises(pay.PaymentError, match="manual_refund_required"):
            pay.refund_order_in_transaction(
                db, user_id=uid, order_id=oid, refund_ref="used-full", now=NOW, settings=cfg
            )
    with Session() as db:
        assert db.get(m.RechargeOrder, oid).status == "paid"
        assert db.query(m.MembershipTerm).one().status == "active"


def test_provider_transaction_cannot_fulfill_second_order(membership_pg_engine, cfg):
    pay, _ = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        first = create(db, uid, cfg)
        deliver(db, event(first, uid), cfg)
        second = create(db, uid, cfg, key="second")
        oid = second.id
    with Session.begin() as db:
        with pytest.raises(pay.PaymentError, match="provider_transaction_conflict"):
            deliver(db, event(db.get(m.RechargeOrder, oid), uid), cfg)
    with Session() as db:
        assert db.get(m.User, uid).credits == 1000
        assert db.get(m.RechargeOrder, oid).status == "pending"


def test_refund_refreshes_term_previously_loaded_before_another_transaction_spends(membership_pg_engine, cfg):
    pay, _ = services()
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        order = create(db, uid, cfg, sku="membership_plus")
        deliver(db, event(order, uid), cfg)
        oid = order.id
        tid = db.query(m.MembershipTerm).one().id
    with Session() as stale:
        cached = stale.get(m.MembershipTerm, tid)
        assert cached.used == 0
        with Session.begin() as newer:
            newer.query(m.User).filter_by(id=uid).with_for_update().one()
            newer.get(m.MembershipTerm, tid).used = 1
        with pytest.raises(pay.PaymentError, match="manual_refund_required"):
            pay.refund_order_in_transaction(
                stale, user_id=uid, order_id=oid, refund_ref="stale-refund", now=NOW, settings=cfg
            )
        stale.rollback()
    with Session() as db:
        assert db.get(m.RechargeOrder, oid).status == "paid"
        assert db.get(m.MembershipTerm, tid).used == 1


@pytest.mark.parametrize("plan_code,term_units,week_units", [("plus", 9030, 3010), ("max", 72240, 24080)])
def test_created_membership_order_fulfills_frozen_entitlement_after_sale_stops(
    membership_pg_engine, cfg, monkeypatch, plan_code, term_units, week_units
):
    pay, _ = services()
    from katrain.web.core.billing_catalog import PLANS
    from katrain.web.core import membership

    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        order = create(db, uid, cfg, sku=f"membership_{plan_code}")
        oid = order.id
        version = order.catalog_version
        payload = event(order, uid)
    cfg.MEMBERSHIP_MAX_SALE_ENABLED = False
    monkeypatch.setitem(PLANS, plan_code, {**PLANS[plan_code], "sellable": False, "term_units": 1, "week_units": 1})
    monkeypatch.setattr(membership, "TERM_DAYS", 1)
    monkeypatch.setattr(membership, "CATALOG_VERSION", "future_catalog")
    with Session.begin() as db:
        assert create(db, uid, cfg, sku=f"membership_{plan_code}").id == oid
        with pytest.raises(pay.PaymentError, match="sku_not_sellable"):
            create(db, uid, cfg, sku=f"membership_{plan_code}", key="after-sale-stopped")
        paid = deliver(db, payload, cfg)
        assert paid.status == "paid"
    with Session() as db:
        term = db.query(m.MembershipTerm).filter_by(order_id=oid).one()
        assert term.plan_id == plan_code and term.limit == term_units and term.catalog_version == version
        assert term.ends_at - term.starts_at == timedelta(days=30)
        assert db.get(m.User, uid).credits == 0
        usage = membership.usage_snapshot(db, user_id=uid, now=NOW, environment="test", payments_mode="mock")
        assert usage["week"]["limit"] == week_units


def test_paid_membership_week_budget_and_quote_use_frozen_order_snapshot(membership_pg_engine, cfg, monkeypatch):
    from katrain.web.core import billing_operations as ops, membership
    from katrain.web.core.billing_catalog import PLANS

    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        order = create(db, uid, cfg, sku="membership_plus")
        deliver(db, event(order, uid), cfg)
        assert order.sku_snapshot["week_units"] == 3010
    monkeypatch.setitem(PLANS, "plus", {**PLANS["plus"], "week_units": 1, "term_units": 1})
    with Session() as db:
        usage = membership.usage_snapshot(db, user_id=uid, now=NOW, environment="test", payments_mode="mock")
        assert usage["term"]["limit"] == 9030
        assert usage["week"]["limit"] == usage["week"]["remaining"] == 3010
        quote = ops.quote_operation(
            db,
            user_id=uid,
            now=NOW,
            kind="report",
            fingerprint="a" * 64,
            profile="normal",
            units=2,
            environment="test",
            secret="frozen-quote-secret",
        )
        assert quote["source"] == "membership"
