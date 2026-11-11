"""One real HTTP -> OTP service -> PostgreSQL ledger journey; only SMS is fake."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import FastAPI
from jose import jwt
from sqlalchemy.orm import sessionmaker

from katrain.web.api.v1.api import api_router
from katrain.web.core import billing, models_db, phone_otp, sms
from sqlalchemy.exc import DBAPIError
from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token, get_password_hash
from katrain.web.core.config import settings
from tests.web_ui.membership_test_support import membership_pg_engine
from tests.web_ui.test_phone_otp_limits_pg import FLOW, PHONE, FakeSender


@pytest.mark.asyncio
async def test_http_phone_signup_and_return_login_share_one_pg_claim_and_grant(membership_pg_engine, monkeypatch):
    sender = FakeSender()
    monkeypatch.setattr(sms, "sender_from_settings", lambda config: sender)
    monkeypatch.setattr(settings, "KATRAIN_SMS_ENABLED", True)
    monkeypatch.setattr(settings, "KATRAIN_SMS_DAILY_LIMIT", 10)
    monkeypatch.setattr(settings, "KATRAIN_ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "SECRET_KEY", "isolated-pg-http-otp-secret-" * 3)
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(phone_otp, "_now", lambda: now)
    sessions = sessionmaker(bind=membership_pg_engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.state.user_repo = SQLAlchemyUserRepository(sessions)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        challenge = await client.post(
            "/api/v1/auth/phone/challenges", json={"phone": PHONE, "purpose": "login", "flow_id": FLOW}
        )
        assert challenge.status_code == 200 and challenge.json()["delivery"] == "sent"
        assert len(sender.calls) == 1 and sender.calls[0][0] == PHONE
        login = await client.post(
            "/api/v1/auth/phone/login",
            json={"challenge_id": challenge.json()["challenge_id"], "code": sender.calls[-1][1], "flow_id": FLOW},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert claims["type"] == "access" and claims["sub"].startswith("u_")
        assert PHONE not in str(claims) and "phone" not in claims
        me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200 and me.json()["credits"] == 5000
        first_user = me.json()
        assert first_user["username"] == claims["sub"] and "phone" not in first_user
        now += timedelta(seconds=61)
        again = await client.post(
            "/api/v1/auth/phone/challenges", json={"phone": PHONE, "purpose": "login", "flow_id": FLOW}
        )
        assert again.status_code == 200 and len(sender.calls) == 2
        relogin = await client.post(
            "/api/v1/auth/phone/login",
            json={"challenge_id": again.json()["challenge_id"], "code": sender.calls[-1][1], "flow_id": FLOW},
        )
        assert relogin.status_code == 200
        again_me = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {relogin.json()['access_token']}"}
        )
        assert again_me.status_code == 200 and again_me.json() == first_user
    with sessions() as db:
        assert db.query(models_db.User).count() == 1
        assert db.query(models_db.PhoneIdentity).count() == 1
        claim = db.query(models_db.PhoneSignupClaim).one()
        transaction = db.query(models_db.CreditTransaction).one()
        assert transaction.ref_id == claim.grant_ref
        assert (transaction.delta, transaction.reason, transaction.balance_after) == (5000, "signup_grant", 5000)
        assert transaction.user_id == first_user["id"]


@pytest.mark.asyncio
async def test_database_failure_rolls_back_signup_and_is_private_at_http_boundary(
    membership_pg_engine, monkeypatch, caplog
):
    sender = FakeSender()
    monkeypatch.setattr(sms, "sender_from_settings", lambda config: sender)
    monkeypatch.setattr(settings, "KATRAIN_SMS_ENABLED", True)
    monkeypatch.setattr(settings, "KATRAIN_SMS_DAILY_LIMIT", 10)
    monkeypatch.setattr(settings, "KATRAIN_ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "SECRET_KEY", "isolated-pg-http-otp-secret-" * 3)
    sessions = sessionmaker(bind=membership_pg_engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.state.user_repo = SQLAlchemyUserRepository(sessions)
    apply_adjustment = billing.apply_adjustment

    def fail_after_ledger_write(*args, **kwargs):
        apply_adjustment(*args, **kwargs)
        raise DBAPIError(
            "UPDATE private_table SET code=:code WHERE phone=:phone",
            {"phone": PHONE, "code": sender.calls[-1][1]},
            RuntimeError("injected database failure"),
        )

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        challenge = await client.post(
            "/api/v1/auth/phone/challenges", json={"phone": PHONE, "purpose": "login", "flow_id": FLOW}
        )
        assert challenge.status_code == 200
        payload = {"challenge_id": challenge.json()["challenge_id"], "code": sender.calls[-1][1], "flow_id": FLOW}
        monkeypatch.setattr(billing, "apply_adjustment", fail_after_ledger_write)
        failure = await client.post("/api/v1/auth/phone/login", json=payload)
        assert failure.status_code == 503 and failure.json() == {"detail": {"code": "sms_unavailable"}}
        assert failure.headers["cache-control"] == "no-store"
        assert PHONE not in failure.text + caplog.text and payload["code"] not in failure.text + caplog.text
        assert all(record.exc_info is None for record in caplog.records)
        with sessions() as db:
            assert db.query(models_db.User).count() == 0
            assert db.query(models_db.PhoneIdentity).count() == 0
            assert db.query(models_db.PhoneSignupClaim).count() == 0
            assert db.query(models_db.CreditTransaction).count() == 0
            assert db.get(models_db.SmsChallenge, payload["challenge_id"]).state == "sent"
        monkeypatch.setattr(billing, "apply_adjustment", apply_adjustment)
        retry = await client.post("/api/v1/auth/phone/login", json=payload)
        assert retry.status_code == 200
    with sessions() as db:
        assert db.query(models_db.User).one().credits == 5000
        assert db.query(models_db.CreditTransaction).count() == 1


@pytest.mark.asyncio
async def test_existing_user_binds_then_otp_login_preserves_identity_and_balance(membership_pg_engine, monkeypatch):
    sender = FakeSender()
    monkeypatch.setattr(sms, "sender_from_settings", lambda config: sender)
    monkeypatch.setattr(settings, "KATRAIN_SMS_ENABLED", True)
    monkeypatch.setattr(settings, "KATRAIN_SMS_DAILY_LIMIT", 10)
    monkeypatch.setattr(settings, "KATRAIN_ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "SECRET_KEY", "isolated-pg-http-otp-secret-" * 3)
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(phone_otp, "_now", lambda: now)
    sessions = sessionmaker(bind=membership_pg_engine, expire_on_commit=False)
    with sessions() as db:
        user = models_db.User(
            username="legacy-bind-owner",
            hashed_password=get_password_hash("existing-password"),
            credits=12345,
            membership_revision=3,
        )
        db.add(user)
        db.commit()
        user_id, user_uuid = user.id, user.uuid
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.state.user_repo = SQLAlchemyUserRepository(sessions)
    headers = {"Authorization": f"Bearer {create_access_token({'sub': 'legacy-bind-owner'})}"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        challenge = await client.post(
            "/api/v1/auth/phone/challenges", json={"phone": PHONE, "purpose": "bind", "flow_id": FLOW}, headers=headers
        )
        assert challenge.status_code == 200 and len(sender.calls) == 1
        payload = {"challenge_id": challenge.json()["challenge_id"], "code": sender.calls[-1][1], "flow_id": FLOW}
        missing = await client.post("/api/v1/auth/phone/bind", json=payload, headers=headers)
        wrong = await client.post(
            "/api/v1/auth/phone/bind", json={**payload, "current_password": "wrong-password"}, headers=headers
        )
        assert missing.status_code == wrong.status_code == 401
        assert missing.json() == wrong.json() == {"detail": {"code": "bind_reauth_failed"}}
        with sessions() as db:
            attempts = db.query(models_db.SmsSendBucket).filter_by(kind="bind_reauth", key=str(user_id)).one()
            assert attempts.count == 2
            assert db.query(models_db.PhoneIdentity).count() == 0
        bound = await client.post(
            "/api/v1/auth/phone/bind", json={**payload, "current_password": "existing-password"}, headers=headers
        )
        assert bound.status_code == 200 and bound.json() == {"bound": True, "masked_phone": "+86 138****0011"}
        status = await client.get("/api/v1/auth/phone/status", headers=headers)
        assert status.status_code == 200 and status.json() == bound.json()
        now += timedelta(seconds=61)
        login_challenge = await client.post(
            "/api/v1/auth/phone/challenges", json={"phone": PHONE, "purpose": "login", "flow_id": FLOW}
        )
        assert login_challenge.status_code == 200
        login = await client.post(
            "/api/v1/auth/phone/login",
            json={"challenge_id": login_challenge.json()["challenge_id"], "code": sender.calls[-1][1], "flow_id": FLOW},
        )
        assert login.status_code == 200
        me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
        assert me.status_code == 200
        assert (me.json()["id"], me.json()["uuid"], me.json()["credits"]) == (user_id, user_uuid, 12345)
    with sessions() as db:
        stored = db.get(models_db.User, user_id)
        assert stored.uuid == user_uuid and stored.credits == 12345 and stored.membership_revision == 3
        assert db.query(models_db.PhoneIdentity).one().user_id == user_id
        assert db.query(models_db.PhoneSignupClaim).one().claim_type == "bound_existing"
        assert db.query(models_db.CreditTransaction).count() == 0
