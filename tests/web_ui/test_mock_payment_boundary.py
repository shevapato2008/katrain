"""Mock payment facts require an independently TEST marked DB and signed admin events."""


def test_mock_event_signature_covers_all_fields():
    from katrain.web.core.payment_mock import sign_event, verify_event
    from katrain.web.core.payments import PaymentError

    event = {"order_id": "1", "amount_fen": 1000}
    signature = sign_event(event, secret="isolated-key")
    verify_event(event, signature=signature, secret="isolated-key")
    with pytest.raises(PaymentError, match="invalid_mock_signature"):
        verify_event({**event, "amount_fen": 1}, signature=signature, secret="isolated-key")


from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import sessionmaker

from tests.web_ui.membership_test_support import membership_pg_engine
from tests.web_ui.test_membership_orders_pg import cfg, seed, create, event, NOW
from katrain.web.core import models_db as m
from katrain.web.core.db import get_db
from katrain.web.api.v1.endpoints.auth import get_current_admin_user


def test_test_routes_not_registered_in_production_or_disabled():
    from katrain.web.api.v1.endpoints.payment_test import register_test_payment_routes

    for environment, mode in [("production", "mock"), ("test", "disabled"), ("production", "disabled")]:
        router = APIRouter()
        register_test_payment_routes(
            router, runtime_settings=SimpleNamespace(KATRAIN_ENVIRONMENT=environment, PAYMENTS_MODE=mode)
        )
        assert router.routes == []


@pytest.fixture
def mock_api(membership_pg_engine, cfg, monkeypatch):
    from katrain.web.api.v1.endpoints import payment_test
    from katrain.web.api.v1.endpoints.payment_test import register_test_payment_routes

    monkeypatch.setattr(payment_test, "_now", lambda: NOW)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    uid = seed(membership_pg_engine)
    adminid = seed(membership_pg_engine, "test-admin")
    with Session.begin() as db:
        db.get(m.User, adminid).is_admin = True
        order = create(db, uid, cfg)
        payload = event(order, uid)
    app = FastAPI()
    register_test_payment_routes(app, runtime_settings=cfg)

    def db_dependency():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_dependency
    app.dependency_overrides[get_current_admin_user] = lambda: SimpleNamespace(id=adminid, is_admin=True)
    app.state.test_session = Session
    app.state.event = payload
    app.state.buyer_id = uid
    app.state.admin_id = adminid
    return app


@pytest.mark.asyncio
async def test_signed_test_admin_event_fulfills_once_and_unsigned_fails(mock_api, cfg):
    from katrain.web.core.payment_mock import sign_event

    data = {**mock_api.state.event, "deliver": True}
    signature = sign_event(data, secret=cfg.PAYMENT_MOCK_EVENT_SECRET)
    async with AsyncClient(transport=ASGITransport(app=mock_api), base_url="http://test") as ac:
        forged = await ac.post("/payments/test/events", json=data, headers={"X-Mock-Signature": "forged"})
        paid = await ac.post("/payments/test/events", json=data, headers={"X-Mock-Signature": signature})
        replay = await ac.post("/payments/test/events", json=data, headers={"X-Mock-Signature": signature})
    assert forged.status_code == 403
    assert paid.status_code == replay.status_code == 200
    assert paid.json()["status"] == "paid"
    assert paid.headers["cache-control"] == "no-store"
    with mock_api.state.test_session() as db:
        assert db.get(m.User, mock_api.state.buyer_id).credits == 1000
        assert db.query(m.CreditTransaction).count() == 1


@pytest.mark.asyncio
async def test_mock_write_rechecks_real_admin_and_actual_database(mock_api, cfg):
    from katrain.web.core.payment_mock import sign_event

    data = {**mock_api.state.event, "deliver": True}
    signature = sign_event(data, secret=cfg.PAYMENT_MOCK_EVENT_SECRET)
    mock_api.dependency_overrides[get_current_admin_user] = lambda: SimpleNamespace(
        id=mock_api.state.buyer_id, is_admin=True
    )
    async with AsyncClient(transport=ASGITransport(app=mock_api), base_url="http://test") as ac:
        denied = await ac.post("/payments/test/events", json=data, headers={"X-Mock-Signature": signature})
        cfg.KATRAIN_ENVIRONMENT = "production"
        production = await ac.post("/payments/test/events", json=data, headers={"X-Mock-Signature": signature})
    assert denied.status_code == 403
    assert production.status_code == 503
    with mock_api.state.test_session() as db:
        assert db.query(m.CreditTransaction).count() == 0


def test_missing_notification_recovers_from_provider_fact_after_checkout_expiry(membership_pg_engine, cfg):
    from katrain.web.core import payments, payment_mock

    uid = seed(membership_pg_engine)
    adminid = seed(membership_pg_engine, "admin-recovery")
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        db.get(m.User, adminid).is_admin = True
        order = create(db, uid, cfg)
        data = event(order, uid)
        oid = order.id
        sig = payment_mock.sign_event({**data, "deliver": False}, secret=cfg.PAYMENT_MOCK_EVENT_SECRET)
        payment_mock.record_event_in_transaction(
            db,
            event=data,
            signature=sig,
            admin_user_id=adminid,
            now=NOW + timedelta(minutes=10),
            settings=cfg,
            deliver=False,
        )
        assert order.status == "pending" and db.get(m.User, uid).credits == 0
    with Session.begin() as db:
        receipt = payments.reconcile_order_in_transaction(
            db, user_id=uid, order_id=oid, now=NOW + timedelta(minutes=20), settings=cfg
        )
        assert receipt.status == "paid"
    with Session() as db:
        assert db.get(m.User, uid).credits == 1000


@pytest.mark.asyncio
async def test_full_refund_requires_signed_identity_and_is_idempotent(mock_api, cfg):
    from katrain.web.core.payment_mock import sign_event

    payload = {**mock_api.state.event, "deliver": True}
    headers = {"X-Mock-Signature": sign_event(payload, secret=cfg.PAYMENT_MOCK_EVENT_SECRET)}
    oid = mock_api.state.event["order_id"]
    async with AsyncClient(transport=ASGITransport(app=mock_api), base_url="http://test") as ac:
        paid = await ac.post("/payments/test/events", json=payload, headers=headers)
        assert paid.status_code == 200
        refund = {key: value for key, value in mock_api.state.event.items() if key not in {"order_id", "status"}}
        refund["refund_ref"] = "refund-signed"
        signature = sign_event({"order_id": oid, **refund}, secret=cfg.PAYMENT_MOCK_EVENT_SECRET)
        forged = await ac.post(
            f"/payments/test/orders/{oid}/refund",
            json={**refund, "amount_fen": 1},
            headers={"X-Mock-Signature": signature},
        )
        assert forged.status_code == 403
        for _ in range(2):
            refunded = await ac.post(
                f"/payments/test/orders/{oid}/refund", json=refund, headers={"X-Mock-Signature": signature}
            )
            assert refunded.status_code == 200 and refunded.json()["status"] == "refunded"
    with mock_api.state.test_session() as db:
        assert db.get(m.User, mock_api.state.buyer_id).credits == 0
        assert db.query(m.CreditTransaction).count() == 2


def test_mock_write_rejects_explicit_database_mismatch(membership_pg_engine, cfg, monkeypatch):
    from katrain.web.core import payments
    import os

    monkeypatch.setenv("KATRAIN_DATABASE_URL", os.environ["TEST_DATABASE_URL"] + "_unknown")
    uid = seed(membership_pg_engine)
    Session = sessionmaker(bind=membership_pg_engine, autoflush=False)
    with Session() as db:
        with pytest.raises(payments.PaymentError, match="mock_database_not_verified"):
            create(db, uid, cfg)
        assert db.query(m.RechargeOrder).count() == 0


def test_development_mock_provider_fact_fits_existing_storage(membership_pg_engine, cfg):
    from katrain.web.core import payment_mock

    cfg.KATRAIN_ENVIRONMENT = "development"
    uid = seed(membership_pg_engine)
    adminid = seed(membership_pg_engine, "dev-admin")
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        db.get(m.User, adminid).is_admin = True
        order = create(db, uid, cfg)
        payload = {**event(order, uid), "environment": "development"}
        sig = payment_mock.sign_event({**payload, "deliver": False}, secret=cfg.PAYMENT_MOCK_EVENT_SECRET)
        payment_mock.record_event_in_transaction(
            db, event=payload, signature=sig, admin_user_id=adminid, now=NOW, settings=cfg, deliver=False
        )
        assert payment_mock.lookup_event(db, order)["provider_tx_id"] == payload["provider_tx_id"]


@pytest.mark.asyncio
async def test_http_buy_pro_pay_receipt_and_usage_form_one_journey(mock_api, cfg, monkeypatch):
    from katrain.web.api.v1.endpoints import billing
    from katrain.web.api.v1.endpoints.auth import get_current_user, require_writable_user
    from katrain.web.core.config import settings
    from katrain.web.core.payment_mock import sign_event

    for key, value in vars(cfg).items():
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(billing, "_now", lambda: NOW)
    buyer = SimpleNamespace(id=mock_api.state.buyer_id, username="buyer", is_admin=False)
    mock_api.dependency_overrides[get_current_user] = lambda: buyer
    mock_api.dependency_overrides[require_writable_user] = lambda: buyer
    mock_api.include_router(billing.router, prefix="/api/v1/billing")
    async with AsyncClient(transport=ASGITransport(app=mock_api), base_url="http://test") as ac:
        created = await ac.post(
            "/api/v1/billing/orders", json={"sku": "membership_pro", "idempotency_key": "pro-http-journey"}
        )
        assert created.status_code == 200, created.text
        order = created.json()
        assert order["status"] == "pending" and order["amount_fen"] == 9900 and order["fulfillment"] is None
        data = {
            "order_id": order["id"],
            "owner_id": buyer.id,
            "environment": "test",
            "amount_fen": 9900,
            "provider_tx_id": "pro-http-tx",
            "status": "paid",
            "deliver": True,
        }
        signature = sign_event(data, secret=cfg.PAYMENT_MOCK_EVENT_SECRET)
        paid = await ac.post("/payments/test/events", json=data, headers={"X-Mock-Signature": signature})
        assert paid.status_code == 200, paid.text
        receipt = await ac.get(f"/api/v1/billing/orders/{order['id']}")
        usage = await ac.get("/api/v1/billing/usage")
    assert receipt.status_code == usage.status_code == 200
    assert receipt.json()["status"] == "paid" and receipt.json()["fulfillment"]["plan_code"] == "pro"
    assert usage.json()["plan"]["current"]["code"] == "pro"
    assert usage.json()["term"]["limit"] == 27090 and usage.json()["week"]["limit"] == 9030
    assert usage.json()["revision"] == 1 and usage.json()["wallet"]["credits"] == 0


def test_late_failed_notification_cannot_override_undelivered_paid_fact(membership_pg_engine, cfg):
    from katrain.web.core import payment_mock

    uid = seed(membership_pg_engine)
    adminid = seed(membership_pg_engine, "late-notify-admin")
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        db.get(m.User, adminid).is_admin = True
        order = create(db, uid, cfg)
        payload = event(order, uid)
        sig = payment_mock.sign_event({**payload, "deliver": False}, secret=cfg.PAYMENT_MOCK_EVENT_SECRET)
        payment_mock.record_event_in_transaction(
            db,
            event=payload,
            signature=sig,
            admin_user_id=adminid,
            now=NOW + timedelta(minutes=10),
            settings=cfg,
            deliver=False,
        )
        oid = order.id
    with Session.begin() as db:
        failure = {**payload, "status": "failed"}
        sig = payment_mock.sign_event({**failure, "deliver": True}, secret=cfg.PAYMENT_MOCK_EVENT_SECRET)
        result = payment_mock.record_event_in_transaction(
            db,
            event=failure,
            signature=sig,
            admin_user_id=adminid,
            now=NOW + timedelta(minutes=20),
            settings=cfg,
            deliver=True,
        )
        assert result.status == "paid"
    with Session() as db:
        assert db.get(m.User, uid).credits == 1000
        assert db.get(m.RechargeOrder, oid).status == "paid"
        assert db.query(m.CreditTransaction).count() == 1
