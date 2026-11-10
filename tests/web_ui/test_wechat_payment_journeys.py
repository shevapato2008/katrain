"""Actual crypto, isolated PG and HTTP; merchant transport is test-only."""

import base64
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.orm import sessionmaker

from tests.web_ui.membership_test_support import membership_pg_engine
from tests.web_ui.test_wechat_native import cfg as native_cfg, keys, signed
from tests.web_ui.test_wechat_orders_pg import NOW
from katrain.web.core import models_db as m


@pytest.fixture
def journey(membership_pg_engine, native_cfg, keys, monkeypatch):
    from katrain.web.api.v1.endpoints import billing, payment_wechat
    from katrain.web.core.config import settings
    from katrain.web.core.db import get_db
    from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token
    from katrain.web.core.wechat_native import WechatNativeClient

    for name, value in {
        **vars(native_cfg),
        "KATRAIN_MODE": "server",
        "KATRAIN_ENVIRONMENT": "test",
        "PAYMENTS_MODE": "live",
        "MEMBERSHIP_MODE": "enabled",
    }.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(billing, "_now", lambda: NOW)
    Session = sessionmaker(bind=membership_pg_engine, autoflush=False)
    with Session.begin() as db:
        users = [
            m.User(username="native-owner", hashed_password="x", credits=0),
            m.User(username="native-other", hashed_password="x", credits=0),
        ]
        db.add_all(users)
        db.flush()
        uid, other = (u.id for u in users)
    stored, calls, query_state = {}, [], {"state": "NOTPAY"}

    def handler(request):
        calls.append(request)
        if request.method == "POST" and request.url.path.endswith("/native"):
            payload = json.loads(request.content)
            stored[payload["out_trade_no"]] = payload
            body = json.dumps({"code_url": "weixin://wxpay/bizpayurl?pr=HTTPJourney"}).encode()
        elif request.method == "GET":
            number = request.url.path.rsplit("/", 1)[-1]
            request_data = stored[number]
            body = json.dumps(
                {
                    "appid": request_data["appid"],
                    "mchid": request_data["mchid"],
                    "out_trade_no": number,
                    "trade_state": query_state["state"],
                    "trade_type": "NATIVE",
                    "transaction_id": "wechat-query-" + number,
                    "amount": request_data["amount"],
                    "success_time": NOW.isoformat(),
                }
            ).encode()
        else:
            body = b""
        return httpx.Response(
            204 if request.url.path.endswith("/close") else 200,
            content=body,
            headers=signed(keys[1], body, timestamp=int(NOW.timestamp())),
        )

    provider = WechatNativeClient.from_settings(
        settings, transport=httpx.MockTransport(handler), clock=lambda: NOW.timestamp()
    )
    monkeypatch.setattr(WechatNativeClient, "from_settings", classmethod(lambda cls, _settings, **kwargs: provider))
    app = FastAPI()
    app.include_router(billing.router, prefix="/api/v1/billing")
    app.include_router(payment_wechat.router, prefix="/api/v1/payments/wechat")
    app.state.user_repo = SQLAlchemyUserRepository(Session)

    def db_dependency():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_dependency
    auth = {"Authorization": "Bearer " + create_access_token({"sub": "native-owner"})}
    other_auth = {"Authorization": "Bearer " + create_access_token({"sub": "native-other"})}

    def notification(oid, *, changes=None):
        with Session() as db:
            order = db.get(m.RechargeOrder, int(oid))
            req = order.payment_details["request"]
            tx = {
                "appid": req["appid"],
                "mchid": req["mchid"],
                "out_trade_no": order.out_trade_no,
                "trade_state": "SUCCESS",
                "trade_type": "NATIVE",
                "transaction_id": "wechat-http-" + str(oid),
                "amount": req["amount"],
                "success_time": NOW.isoformat(),
                **(changes or {}),
            }
        nonce = b"123456789012"
        encrypted = AESGCM(provider.config.api_v3_key).encrypt(nonce, json.dumps(tx).encode(), b"transaction")
        body = json.dumps(
            {
                "id": "notification-" + str(oid),
                "event_type": "TRANSACTION.SUCCESS",
                "resource_type": "encrypt-resource",
                "resource": {
                    "original_type": "transaction",
                    "algorithm": "AEAD_AES_256_GCM",
                    "nonce": nonce.decode(),
                    "associated_data": "transaction",
                    "ciphertext": base64.b64encode(encrypted).decode(),
                },
            }
        ).encode()
        return body, signed(keys[1], body, timestamp=int(NOW.timestamp()))

    return SimpleNamespace(
        app=app,
        Session=Session,
        uid=uid,
        auth=auth,
        other_auth=other_auth,
        notify=notification,
        calls=calls,
        settings=settings,
        query_state=query_state,
    )


@pytest.mark.parametrize("sku", ["topup_10", "membership_plus"])
async def test_http_native_crypto_notify_membership_and_topup(journey, sku):
    j = journey
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=j.app), base_url="http://local.test") as client:
        result = await client.post(
            "/api/v1/billing/orders", headers=j.auth, json={"sku": sku, "provider": "wechat", "idempotency_key": sku}
        )
        assert result.status_code == 200, result.text
        receipt = result.json()
        assert receipt["provider"] == "wechat" and receipt["payment_url"].startswith("weixin://")
        assert result.headers["cache-control"] == "no-store"
        oid = receipt["id"]
        assert (await client.get("/api/v1/billing/orders/" + oid, headers=j.other_auth)).status_code == 404
        assert (await client.post(f"/api/v1/billing/orders/{oid}/cancel", headers=j.other_auth)).status_code == 404
        # A list reads local state and must never fan out into merchant requests.
        before = len(j.calls)
        assert (await client.get("/api/v1/billing/orders", headers=j.auth)).status_code == 200
        assert len(j.calls) == before
        body, headers = j.notify(oid)
        j.settings.PAYMENTS_MODE, j.settings.MEMBERSHIP_MODE = "disabled", "paused"
        for _ in range(2):
            response = await client.post("/api/v1/payments/wechat/notify", content=body, headers=headers)
            assert response.status_code == 204, response.text
            assert response.headers["cache-control"] == "no-store" and response.content == b""
        paid = (await client.get("/api/v1/billing/orders/" + oid, headers=j.auth)).json()
        assert paid["status"] == "paid" and paid["payment_url"] is None
        unavailable = await client.post(
            "/api/v1/billing/orders",
            headers=j.auth,
            json={"sku": sku, "provider": "wechat", "idempotency_key": "new-disabled"},
        )
        assert unavailable.status_code == 503
    with j.Session() as db:
        if sku == "topup_10":
            assert db.get(m.User, j.uid).credits == 1000 and db.query(m.CreditTransaction).count() == 1
        else:
            assert db.query(m.MembershipTerm).count() == 1


async def test_callback_size_signature_event_cloud_boundary(journey):
    j = journey
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=j.app), base_url="http://local.test") as client:
        receipt = (
            await client.post(
                "/api/v1/billing/orders",
                headers=j.auth,
                json={"sku": "topup_10", "provider": "wechat", "idempotency_key": "callback"},
            )
        ).json()
        body, headers = j.notify(receipt["id"])
        bad = await client.post("/api/v1/payments/wechat/notify", content=body + b" ", headers=headers)
        assert bad.status_code == 400 and bad.headers["cache-control"] == "no-store"
        invalid_body, valid_headers = j.notify(receipt["id"], changes={"trade_state": "NOTPAY"})
        assert (
            await client.post("/api/v1/payments/wechat/notify", content=invalid_body, headers=valid_headers)
        ).status_code == 400

        async def large_stream():
            yield b"x" * 32768
            yield b"x" * 32769

        assert (await client.post("/api/v1/payments/wechat/notify", content=large_stream())).status_code == 413
        j.settings.KATRAIN_MODE = "board"
        assert (await client.post("/api/v1/payments/wechat/notify", content=body, headers=headers)).status_code == 404
    with j.Session() as db:
        assert db.get(m.User, j.uid).credits == 0


async def test_signed_query_compensates_without_callback_and_cancel_is_signed(journey, monkeypatch):
    from datetime import timedelta
    from katrain.web.api.v1.endpoints import billing

    j = journey
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=j.app), base_url="http://local.test") as client:
        receipt = (
            await client.post(
                "/api/v1/billing/orders",
                headers=j.auth,
                json={"sku": "topup_10", "provider": "wechat", "idempotency_key": "query"},
            )
        ).json()
        j.query_state["state"] = "SUCCESS"
        j.settings.PAYMENTS_MODE, j.settings.MEMBERSHIP_MODE = "disabled", "paused"
        monkeypatch.setattr(billing, "_now", lambda: NOW + timedelta(seconds=6))
        paid = await client.get("/api/v1/billing/orders/" + receipt["id"], headers=j.auth)
        assert paid.status_code == 200 and paid.json()["status"] == "paid"
        j.settings.PAYMENTS_MODE, j.settings.MEMBERSHIP_MODE = "live", "enabled"
        next_order = (
            await client.post(
                "/api/v1/billing/orders",
                headers=j.auth,
                json={"sku": "topup_10", "provider": "wechat", "idempotency_key": "cancel"},
            )
        ).json()
        j.query_state["state"] = "NOTPAY"
        closed = await client.post(f"/api/v1/billing/orders/{next_order['id']}/cancel", headers=j.auth, json={})
        assert closed.status_code == 200 and closed.json()["status"] == "cancelled"
        assert any(call.url.path.endswith("/close") for call in j.calls)


async def test_callback_lock_contention_is_retryable_before_ack(journey):
    j = journey
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=j.app), base_url="http://local.test") as client:
        receipt = (
            await client.post(
                "/api/v1/billing/orders",
                headers=j.auth,
                json={"sku": "topup_10", "provider": "wechat", "idempotency_key": "locked"},
            )
        ).json()
        body, headers = j.notify(receipt["id"])
        with j.Session.begin() as locked:
            locked.query(m.User).filter_by(id=j.uid).with_for_update().one()
            retry = await client.post("/api/v1/payments/wechat/notify", content=body, headers=headers)
            assert retry.status_code == 503 and retry.headers["cache-control"] == "no-store"
        assert (await client.post("/api/v1/payments/wechat/notify", content=body, headers=headers)).status_code == 204
    with j.Session() as db:
        assert db.get(m.User, j.uid).credits == 1000 and db.query(m.CreditTransaction).count() == 1


def test_real_client_unknown_create_restores_frozen_request_after_config_rotation(
    membership_pg_engine, native_cfg, keys
):
    from copy import deepcopy
    from datetime import timedelta
    from katrain.web.core import wechat_payments as wx
    from katrain.web.core.wechat_native import WechatNativeClient

    cfg = SimpleNamespace(
        **vars(native_cfg),
        KATRAIN_ENVIRONMENT="test",
        PAYMENTS_MODE="live",
        MEMBERSHIP_MODE="enabled",
        MEMBERSHIP_MAX_SALE_ENABLED=True,
    )
    Session = sessionmaker(bind=membership_pg_engine, autoflush=False)
    with Session.begin() as db:
        user = m.User(username="rotation-buyer", hashed_password="x", credits=0)
        db.add(user)
        db.flush()
        uid = user.id
    requests = []

    def provider(request):
        if request.method == "GET":
            return httpx.Response(404, json={"code": "ORDER_NOT_EXIST"})
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            raise httpx.ReadTimeout("test-only lost response")
        body = b'{"code_url":"weixin://wxpay/bizpayurl?pr=FrozenRecovery"}'
        return httpx.Response(200, content=body, headers=signed(keys[1], body, timestamp=int(NOW.timestamp())))

    transport = httpx.MockTransport(provider)
    with Session() as db:
        old_client = WechatNativeClient.from_settings(cfg, transport=transport, clock=lambda: NOW.timestamp())
        unknown = wx.create_order(
            db, user_id=uid, sku="topup_10", idempotency_key="frozen", now=NOW, settings=cfg, client=old_client
        )
        assert unknown["status"] == "pending" and unknown["payment_url"] is None
        frozen = deepcopy(requests[0])
        cfg.WECHAT_PAY_APP_ID = "wx9876543210abcdef"
        cfg.WECHAT_PAY_NOTIFY_URL = "https://merchant.example/new-notify"
        new_client = WechatNativeClient.from_settings(cfg, transport=transport, clock=lambda: NOW.timestamp())
        ready = wx.reconcile_order(
            db, user_id=uid, order_id=unknown["id"], now=NOW + timedelta(seconds=6), settings=cfg, client=new_client
        )
        assert ready["payment_url"] == "weixin://wxpay/bizpayurl?pr=FrozenRecovery"
        assert len(requests) == 2 and requests[1] == frozen
        row = db.get(m.RechargeOrder, int(unknown["id"]))
        assert row.payment_details["request"] == frozen and row.out_trade_no == frozen["out_trade_no"]
