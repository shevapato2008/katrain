"""Real isolated PostgreSQL Native order state and fulfillment invariants."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker

from tests.web_ui.membership_test_support import membership_pg_engine
from katrain.web.core import models_db as m

NOW = datetime(2026, 11, 8, 3, tzinfo=timezone.utc)


@pytest.fixture
def setup(membership_pg_engine):
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        user = m.User(username="wechat-buyer", hashed_password="x", credits=0)
        db.add(user)
        db.flush()
        uid = user.id
    cfg = SimpleNamespace(
        KATRAIN_ENVIRONMENT="test", PAYMENTS_MODE="live", MEMBERSHIP_MODE="enabled", MEMBERSHIP_MAX_SALE_ENABLED=True
    )
    client = SimpleNamespace(
        config=SimpleNamespace(app_id="app-test", mch_id="merchant-test", notify_url="https://example.test/notify")
    )
    return Session, uid, cfg, client


def create(db, uid, cfg, client, sku="topup_10", key="buy"):
    from katrain.web.core import wechat_payments as wx

    return wx.create_intent_in_transaction(
        db, user_id=uid, sku=sku, idempotency_key=key, now=NOW, settings=cfg, client=client
    )


def fact(order, **overrides):
    return {
        "appid": "app-test",
        "mchid": "merchant-test",
        "out_trade_no": order.out_trade_no,
        "trade_state": "SUCCESS",
        "trade_type": "NATIVE",
        "transaction_id": "wx-transaction-1",
        "amount": {"total": order.amount_fen, "currency": "CNY"},
        "success_time": NOW.isoformat(),
        **overrides,
    }


@pytest.mark.parametrize("sku", ["topup_10", "membership_plus"])
def test_native_snapshot_one_unresolved_order_and_atomic_duplicate_grant(setup, sku):
    from katrain.web.core import wechat_payments as wx, payments

    Session, uid, cfg, client = setup
    with Session.begin() as db:
        order = create(db, uid, cfg, client, sku=sku)
        oid = order.id
        payload = fact(order)
        assert len(order.out_trade_no) <= 32 and order.out_trade_no.isascii()
        assert order.payment_details["request"]["time_expire"] == (NOW + timedelta(minutes=15)).isoformat()
        assert create(db, uid, cfg, client, sku=sku, key="different").id == oid
        with pytest.raises(payments.PaymentError, match="unresolved_payment_order"):
            create(db, uid, cfg, client, sku="topup_30", key="other")
    barrier = Barrier(2)

    def deliver(_):
        with Session.begin() as db:
            barrier.wait()
            return wx.apply_transaction_in_transaction(db, transaction=payload, now=NOW, settings=cfg).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(deliver, range(2))) == ["paid", "paid"]
    with Session() as db:
        assert db.get(m.RechargeOrder, oid).status == "paid"
        if sku == "topup_10":
            assert db.get(m.User, uid).credits == 1000 and db.query(m.CreditTransaction).count() == 1
        else:
            assert db.query(m.MembershipTerm).count() == 1


@pytest.mark.parametrize(
    "override",
    [
        {"appid": "other"},
        {"mchid": "other"},
        {"trade_type": "JSAPI"},
        {"amount": {"total": True, "currency": "CNY"}},
        {"amount": {"total": 1, "currency": "CNY"}},
        {"amount": {"total": 1000, "currency": "USD"}},
        {"transaction_id": ""},
    ],
)
def test_frozen_success_binding_and_rollback(setup, override):
    from katrain.web.core import wechat_payments as wx, payments

    Session, uid, cfg, client = setup
    with Session.begin() as db:
        payload = fact(create(db, uid, cfg, client), **override)
    with pytest.raises(payments.PaymentError):
        with Session.begin() as db:
            wx.apply_transaction_in_transaction(db, transaction=payload, now=NOW, settings=cfg)
    with Session() as db:
        assert db.get(m.User, uid).credits == 0 and db.query(m.RechargeOrder).one().status == "pending"


def test_late_success_disabled_and_full_transaction_rollback(setup):
    from katrain.web.core import wechat_payments as wx

    Session, uid, cfg, client = setup
    with Session.begin() as db:
        order = create(db, uid, cfg, client)
        payload = fact(order)
        order.status = "cancelled"
    cfg.PAYMENTS_MODE = "disabled"
    cfg.MEMBERSHIP_MODE = "paused"
    with pytest.raises(RuntimeError):
        with Session.begin() as db:
            wx.apply_transaction_in_transaction(db, transaction=payload, now=NOW + timedelta(hours=1), settings=cfg)
            raise RuntimeError("rollback")
    with Session() as db:
        assert db.get(m.User, uid).credits == 0 and db.query(m.CreditTransaction).count() == 0
    with Session.begin() as db:
        assert (
            wx.apply_transaction_in_transaction(
                db, transaction=payload, now=NOW + timedelta(hours=1), settings=cfg
            ).status
            == "paid"
        )
        wx.apply_transaction_in_transaction(
            db, transaction={**payload, "trade_state": "CLOSED"}, now=NOW + timedelta(hours=1), settings=cfg
        )
        assert db.query(m.RechargeOrder).one().status == "paid"


def test_cancel_proxy_has_identity_bound_path():
    from katrain.web.core.remote_client import RemoteAPIClient
    from katrain.web.core.repository import RepositoryDispatcher

    assert callable(getattr(RemoteAPIClient, "billing_cancel_order", None))
    assert callable(getattr(RepositoryDispatcher, "billing_cancel_order", None))


def test_wechat_callback_registered_without_test_feature_gate():
    from katrain.web.api.v1.api import api_router

    assert any(getattr(r, "path", None) == "/payments/wechat/notify" for r in api_router.routes)


def test_restored_second_key_remains_idempotent_after_payment(setup):
    Session, uid, cfg, client = setup
    from katrain.web.core import wechat_payments as wx

    with Session.begin() as db:
        first = create(db, uid, cfg, client)
        assert create(db, uid, cfg, client, key="restore-key").id == first.id
        wx.apply_transaction_in_transaction(db, transaction=fact(first), now=NOW, settings=cfg)
        assert create(db, uid, cfg, client, key="restore-key").id == first.id


def test_success_rejects_cross_environment(setup):
    Session, uid, cfg, client = setup
    from katrain.web.core import wechat_payments as wx, payments

    with Session.begin() as db:
        payload = fact(create(db, uid, cfg, client))
    cfg.KATRAIN_ENVIRONMENT = "production"
    with pytest.raises(payments.PaymentError):
        with Session.begin() as db:
            wx.apply_transaction_in_transaction(db, transaction=payload, now=NOW, settings=cfg)


class Provider:
    def __init__(self, db, Session, config):
        self.db, self.Session, self.config = db, Session, config
        self.created, self.closed, self.queries = [], [], []
        self.query_result = "NOTPAY"
        self.create_error = False

    def _outside(self, number):
        assert not self.db.in_transaction(), "provider network held a DB transaction"
        with self.Session.begin() as check:
            row = check.query(m.RechargeOrder).filter_by(out_trade_no=number).one()
            # Also prove no user/order row lock survives into the network stage.
            check.query(m.User).filter_by(id=row.user_id).with_for_update(nowait=True).one()
            check.query(m.RechargeOrder).filter_by(id=row.id).with_for_update(nowait=True).one()

    def create_native(self, request):
        from katrain.web.core.wechat_native import WechatNativeError

        self._outside(request["out_trade_no"])
        self.created.append(request)
        if self.create_error:
            raise WechatNativeError("transport_error")
        return "weixin://wxpay/bizpayurl?pr=NativeTest"

    def query(self, number):
        from katrain.web.core.wechat_native import WechatNativeError

        self._outside(number)
        self.queries.append(number)
        if self.query_result == "404":
            raise WechatNativeError("provider_error", status_code=404)
        with self.Session() as check:
            row = check.query(m.RechargeOrder).filter_by(out_trade_no=number).one()
            return fact(row, trade_state=self.query_result)

    def close(self, number):
        self._outside(number)
        self.closed.append(number)


def test_unknown_create_same_parameters_throttle_and_cancel_404_stays_pending(setup):
    from katrain.web.core import wechat_payments as wx

    Session, uid, cfg, binding = setup
    with Session() as db:
        client = Provider(db, Session, binding.config)
        client.create_error = True
        result = wx.create_order(
            db, user_id=uid, sku="topup_10", idempotency_key="buy", now=NOW, settings=cfg, client=client
        )
        assert result["status"] == "pending" and result["payment_url"] is None
        oid = result["id"]
        client.query_result = "404"
        wx.reconcile_order(db, user_id=uid, order_id=oid, now=NOW, settings=cfg, client=client)
        assert client.queries == []
        client.create_error = False
        ready = wx.reconcile_order(
            db, user_id=uid, order_id=oid, now=NOW + timedelta(seconds=6), settings=cfg, client=client
        )
        assert ready["payment_url"] and client.created[0] == client.created[1]
        cancelled = wx.cancel_order(
            db, user_id=uid, order_id=oid, now=NOW + timedelta(seconds=7), settings=cfg, client=client
        )
        assert cancelled["status"] == "pending" and cancelled["cancel_requested"] and cancelled["payment_url"] is None
        expired = wx.reconcile_order(
            db, user_id=uid, order_id=oid, now=NOW + timedelta(hours=1), settings=cfg, client=client
        )
        assert expired["status"] == "pending" and len(client.created) == 2 and client.closed == []


def test_cancel_signed_close_and_disabled_success_query(setup):
    from katrain.web.core import wechat_payments as wx

    Session, uid, cfg, binding = setup
    with Session() as db:
        client = Provider(db, Session, binding.config)
        order = wx.create_order(
            db, user_id=uid, sku="topup_10", idempotency_key="buy", now=NOW, settings=cfg, client=client
        )
        result = wx.cancel_order(db, user_id=uid, order_id=order["id"], now=NOW, settings=cfg, client=client)
        assert result["status"] == "cancelled" and len(client.closed) == 1
        paid = wx.create_order(
            db, user_id=uid, sku="membership_plus", idempotency_key="next", now=NOW, settings=cfg, client=client
        )
        cfg.PAYMENTS_MODE, cfg.MEMBERSHIP_MODE = "disabled", "paused"
        client.query_result = "SUCCESS"
        settled = wx.reconcile_order(
            db, user_id=uid, order_id=paid["id"], now=NOW + timedelta(seconds=6), settings=cfg, client=client
        )
        assert settled["status"] == "paid" and settled["fulfillment"]["plan_code"] == "plus"
        assert settled["payments_mode"] == "live"


def test_cancel_during_inflight_create_cannot_be_terminal_or_recreate(setup):
    from threading import Event
    from katrain.web.core import wechat_payments as wx

    Session, uid, cfg, binding = setup
    entered, release = Event(), Event()
    receipts = []

    def original():
        with Session() as db:
            client = Provider(db, Session, binding.config)
            create_native = client.create_native

            def held(request):
                result = create_native(request)
                entered.set()
                assert release.wait(5)
                return result

            client.create_native = held
            receipts.append(
                wx.create_order(
                    db, user_id=uid, sku="topup_10", idempotency_key="buy", now=NOW, settings=cfg, client=client
                )
            )

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(original)
        try:
            assert entered.wait(5)
            with Session() as db:
                oid = db.query(m.RechargeOrder.id).scalar()
                client = Provider(db, Session, binding.config)
                result = wx.cancel_order(db, user_id=uid, order_id=oid, now=NOW, settings=cfg, client=client)
                assert result["status"] == "pending" and result["payment_url"] is None
            release.set()
            future.result(timeout=5)
        finally:
            release.set()
    assert receipts[0]["status"] == "pending" and receipts[0]["cancel_requested"]
    with Session() as db:
        client = Provider(db, Session, binding.config)
        final = wx.reconcile_order(
            db, user_id=uid, order_id=oid, now=NOW + timedelta(seconds=6), settings=cfg, client=client
        )
        assert final["status"] == "cancelled" and client.created == []


def test_sweep_rotates_due_orders_and_isolates_invalid_fact(setup):
    from katrain.web.core import wechat_payments as wx

    Session, uid, cfg, binding = setup
    ids = []
    with Session.begin() as db:
        for index in range(4):
            user = m.User(username=f"sweep-{index}", hashed_password="x", credits=0)
            db.add(user)
            db.flush()
            order = create(db, user.id, cfg, binding, key=str(index))
            order.payment_details = {**order.payment_details, "create_attempted": True}
            ids.append(order.id)
    calls = []

    def query(number):
        calls.append(number)
        with Session() as check:
            row = check.query(m.RechargeOrder).filter_by(out_trade_no=number).one()
            return fact(row, appid="invalid" if row.id == ids[0] else "app-test", trade_state="NOTPAY")

    client = SimpleNamespace(config=binding.config, query=query)
    assert wx.reconcile_due_orders(Session, now=NOW, settings=cfg, limit=2, client=client) == 1
    assert wx.reconcile_due_orders(Session, now=NOW, settings=cfg, limit=2, client=client) == 2
    assert len(set(calls)) == 4


def test_never_sent_intent_can_cancel_or_expire_without_provider_proof(setup):
    from katrain.web.core import wechat_payments as wx

    Session, uid, cfg, binding = setup
    with Session.begin() as db:
        oid = create(db, uid, cfg, binding).id
    with Session() as db:
        client = Provider(db, Session, binding.config)
        client.query_result = "404"
        cancelled = wx.cancel_order(db, user_id=uid, order_id=oid, now=NOW, settings=cfg, client=client)
        assert cancelled["status"] == "cancelled" and client.queries == []
    with Session.begin() as db:
        oid = create(db, uid, cfg, binding, key="later").id
    with Session() as db:
        client = Provider(db, Session, binding.config)
        expired = wx.reconcile_order(
            db, user_id=uid, order_id=oid, now=NOW + timedelta(hours=1), settings=cfg, client=client
        )
        assert expired["status"] == "expired" and client.queries == []


def test_provider_transaction_uniqueness_rolls_back_competing_user_grant(setup):
    from katrain.web.core import wechat_payments as wx, payments
    from sqlalchemy.exc import IntegrityError

    Session, uid, cfg, client = setup
    with Session.begin() as db:
        first = create(db, uid, cfg, client)
        other = m.User(username="second-buyer", hashed_password="x", credits=0)
        db.add(other)
        db.flush()
        second = create(db, other.id, cfg, client)
        payloads = [fact(first), fact(second)]
    barrier = Barrier(2)

    def finish(index):
        try:
            with Session.begin() as db:
                barrier.wait()
                return wx.apply_transaction_in_transaction(
                    db, transaction=payloads[index], now=NOW, settings=cfg
                ).status
        except (payments.PaymentError, IntegrityError):
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(finish, range(2))) == ["conflict", "paid"]
    with Session() as db:
        assert sum(user.credits for user in db.query(m.User).all()) == 1000
        assert db.query(m.CreditTransaction).count() == 1
        assert sorted(order.status for order in db.query(m.RechargeOrder).all()) == ["paid", "pending"]


def test_bad_current_merchant_binding_rotates_sweep_without_network(setup):
    from katrain.web.core import wechat_payments as wx

    Session, uid, cfg, binding = setup
    with Session.begin() as db:
        oid = create(db, uid, cfg, binding).id
    with Session() as db:
        client = Provider(db, Session, SimpleNamespace(mch_id="changed-merchant"))
        result = wx.reconcile_order(db, user_id=uid, order_id=oid, now=NOW, settings=cfg, client=client)
        assert result["status"] == "pending" and client.queries == [] and client.created == []
    with Session() as db:
        assert db.get(m.RechargeOrder, oid).payment_next_check_at > NOW


def test_payment_wins_cancel_close_race_without_downgrade(setup):
    from katrain.web.core import wechat_payments as wx

    Session, uid, cfg, binding = setup
    with Session() as db:
        client = Provider(db, Session, binding.config)
        receipt = wx.create_order(
            db, user_id=uid, sku="topup_10", idempotency_key="buy", now=NOW, settings=cfg, client=client
        )
        signed_close = client.close

        def close_after_payment(number):
            signed_close(number)
            with Session.begin() as paid:
                row = paid.query(m.RechargeOrder).filter_by(out_trade_no=number).one()
                wx.apply_transaction_in_transaction(paid, transaction=fact(row), now=NOW, settings=cfg)

        client.close = close_after_payment
        result = wx.cancel_order(db, user_id=uid, order_id=receipt["id"], now=NOW, settings=cfg, client=client)
        assert result["status"] == "paid" and result["fulfillment"]["credits"] == 1000
    with Session() as db:
        assert db.get(m.User, uid).credits == 1000 and db.query(m.CreditTransaction).count() == 1


def test_native_second_precision_payment_accepts_same_creation_second(setup):
    from katrain.web.core import wechat_payments as wx

    Session, uid, cfg, client = setup
    created_at = NOW + timedelta(microseconds=123456)
    with Session.begin() as db:
        order = wx.create_intent_in_transaction(
            db, user_id=uid, sku="topup_10", idempotency_key="fraction", now=created_at, settings=cfg, client=client
        )
        assert order.expires_at.microsecond == 0
        assert "." not in order.payment_details["request"]["time_expire"]
        assert (
            wx.apply_transaction_in_transaction(db, transaction=fact(order), now=created_at, settings=cfg).status
            == "paid"
        )


@pytest.mark.parametrize("state", ["PAYERROR", "REVOKED", "USERPAYING", "REFUND"])
def test_non_native_or_refund_observation_requires_review_without_grant(setup, state):
    from katrain.web.core import wechat_payments as wx

    Session, uid, cfg, client = setup
    with Session.begin() as db:
        order = create(db, uid, cfg, client)
        result = wx.apply_transaction_in_transaction(
            db, transaction=fact(order, trade_state=state), now=NOW, settings=cfg
        )
        assert result.status == "pending" and result.payment_details["provider_attention"]
        assert db.get(m.User, uid).credits == 0


def test_query_crossing_expiry_never_recreates_and_receipt_advances_clock(setup, monkeypatch):
    from katrain.web.core import wechat_payments as wx
    from katrain.web.core.wechat_native import WechatNativeError

    Session, uid, cfg, binding = setup
    ticks = [0.0]
    monkeypatch.setattr(wx, "monotonic", lambda: ticks[0], raising=False)
    with Session.begin() as db:
        order = create(db, uid, cfg, binding)
        order.payment_details = {**order.payment_details, "create_attempted": True}
        oid = order.id
    with Session() as db:
        client = Provider(db, Session, binding.config)

        def query_after_deadline(number):
            client._outside(number)
            ticks[0] += 2
            raise WechatNativeError("provider_error", status_code=404)

        client.query = query_after_deadline
        result = wx.reconcile_order(
            db, user_id=uid, order_id=oid, now=NOW + timedelta(minutes=15, seconds=-1), settings=cfg, client=client
        )
        assert client.created == [] and result["status"] == "pending" and result["payment_url"] is None
        assert datetime.fromisoformat(result["server_now"]) == NOW + timedelta(minutes=15, seconds=1)


def test_sweep_elapsed_budget_stops_before_next_network_and_preserves_fair_due(setup, monkeypatch):
    from katrain.web.core import wechat_payments as wx

    Session, uid, cfg, binding = setup
    ticks = [0.0]
    monkeypatch.setattr(wx, "monotonic", lambda: ticks[0])
    ids = []
    with Session.begin() as db:
        for index in range(3):
            user = m.User(username=f"budget-{index}", hashed_password="x", credits=0)
            db.add(user)
            db.flush()
            order = create(db, user.id, cfg, binding, key=str(index))
            order.payment_details = {**order.payment_details, "create_attempted": True}
            ids.append(order.id)
    calls = []

    def slow_query(number):
        calls.append(number)
        ticks[0] += 30
        with Session() as db:
            row = db.query(m.RechargeOrder).filter_by(out_trade_no=number).one()
            return fact(row, trade_state="NOTPAY")

    client = SimpleNamespace(config=binding.config, query=slow_query)
    assert wx.reconcile_due_orders(Session, now=NOW, settings=cfg, limit=20, client=client) == 1
    assert len(calls) == 1
    with Session() as db:
        assert db.get(m.RechargeOrder, ids[1]).payment_next_check_at == NOW


def test_late_create_response_hides_qr_and_advances_receipt_time(setup, monkeypatch):
    from katrain.web.core import wechat_payments as wx

    Session, uid, cfg, binding = setup
    ticks = [0.0]
    monkeypatch.setattr(wx, "monotonic", lambda: ticks[0])
    with Session.begin() as db:
        oid = create(db, uid, cfg, binding).id
    with Session() as db:
        client = Provider(db, Session, binding.config)
        native_create = client.create_native

        def late(request):
            code_url = native_create(request)
            ticks[0] += 100
            return code_url

        client.create_native = late
        result = wx.reconcile_order(
            db, user_id=uid, order_id=oid, now=NOW + timedelta(minutes=15, seconds=-90), settings=cfg, client=client
        )
        assert len(client.created) == 1 and result["status"] == "pending" and result["payment_url"] is None
        assert datetime.fromisoformat(result["server_now"]) == NOW + timedelta(minutes=15, seconds=10)


@pytest.mark.parametrize("remaining,expected_creates", [(79, 0), (80, 0), (81, 1)])
def test_native_create_requires_official_expiry_clamp_margin(setup, monkeypatch, remaining, expected_creates):
    from katrain.web.core import wechat_payments as wx

    Session, uid, cfg, binding = setup
    monkeypatch.setattr(wx, "monotonic", lambda: 0.0)
    with Session.begin() as db:
        oid = create(db, uid, cfg, binding).id
    with Session() as db:
        client = Provider(db, Session, binding.config)
        client.query_result = "404"
        result = wx.reconcile_order(
            db,
            user_id=uid,
            order_id=oid,
            now=NOW + timedelta(minutes=15, seconds=-remaining),
            settings=cfg,
            client=client,
        )
        assert len(client.created) == expected_creates
        assert result["status"] == "pending"
