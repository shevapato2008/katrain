"""Real HTTP continuation/password boundary; only SMS delivery is substituted."""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from katrain.web.api.v1.api import api_router
from katrain.web.core import models_db, sms
from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token, get_password_hash
from katrain.web.core.config import settings
from katrain.web.core.migrations import migrate_public_username_schema
from tests.web_ui.membership_test_support import membership_pg_engine
from tests.web_ui.test_phone_continue_pg import PASSWORD, NEW_PASSWORD
from tests.web_ui.test_phone_auth_remote import client_with_handler
from tests.web_ui.test_phone_otp_limits_pg import FLOW, PHONE, FakeSender


@pytest.fixture
def phone_app(membership_pg_engine, monkeypatch):
    sender = FakeSender()
    monkeypatch.setattr(sms, "sender_from_settings", lambda config: sender)
    monkeypatch.setattr(settings, "KATRAIN_SMS_ENABLED", True)
    monkeypatch.setattr(settings, "KATRAIN_SMS_DAILY_LIMIT", 10)
    monkeypatch.setattr(settings, "KATRAIN_ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "SECRET_KEY", "isolated-pg-http-otp-secret-" * 3)
    migrate_public_username_schema(membership_pg_engine, mode="server")
    sessions = sessionmaker(bind=membership_pg_engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.state.user_repo = SQLAlchemyUserRepository(sessions)
    return app, sender, sessions


async def http_proof(client, sender):
    response = await client.post(
        "/api/v1/auth/phone/challenges", json={"phone": PHONE, "purpose": "login", "flow_id": FLOW}
    )
    assert response.status_code == 200
    return {"challenge_id": response.json()["challenge_id"], "code": sender.calls[-1][1], "flow_id": FLOW}


@pytest.mark.asyncio
async def test_http_continue_then_optional_password_normal_login_keeps_same_account(phone_app):
    app, sender, sessions = phone_app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        values = await http_proof(client, sender)
        result = await client.post("/api/v1/auth/phone/continue", json={**values, "public_username": "新棋手"})
        assert result.status_code == 200, "new continuation endpoint must accept a name without a password"
        assert result.json()["signup_grant_credits"] == 5000 and result.headers["cache-control"] == "no-store"
        access = result.json()["access_token"]
        headers = {"Authorization": f"Bearer {access}"}
        me = await client.get("/api/v1/auth/me", headers=headers)
        user_id = me.json()["id"]
        with sessions() as db, db.begin():
            from datetime import timedelta

            db.get(models_db.SmsPhoneState, PHONE).last_send_at -= timedelta(seconds=61)
        fresh = await http_proof(client, sender)
        changed = await client.post(
            "/api/v1/auth/phone/password", headers=headers, json={**fresh, "new_password": NEW_PASSWORD}
        )
        assert changed.status_code == 204 and changed.content == b"" and changed.headers["cache-control"] == "no-store"
        assert (await client.get("/api/v1/auth/me", headers=headers)).json() == me.json()
        password_login = await client.post("/api/v1/auth/login", json={"username": "新棋手", "password": NEW_PASSWORD})
        assert password_login.status_code == 200
        password_me = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {password_login.json()['access_token']}"}
        )
        assert password_me.json()["id"] == user_id
    with sessions() as db:
        assert db.query(models_db.CreditTransaction).count() == db.query(models_db.PhoneSignupClaim).count() == 1


@pytest.mark.asyncio
async def test_http_existing_name_conflicts_are_private_and_proof_is_reusable(phone_app, caplog):
    app, sender, sessions = phone_app
    with sessions() as db, db.begin():
        user = models_db.User(username="old account.name", hashed_password=get_password_hash(PASSWORD), credits=321)
        db.add(user)
        db.flush()
        user_id = user.id
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        values = await http_proof(client, sender)
        body = {**values, "public_username": "old account.name"}
        required = await client.post("/api/v1/auth/phone/continue", json=body)
        assert required.status_code == 409 and required.json() == {"detail": {"code": "account_password_required"}}
        wrong = await client.post("/api/v1/auth/phone/continue", json={**body, "current_password": "private-wrong"})
        assert wrong.status_code == 401 and wrong.json() == {"detail": {"code": "bind_reauth_failed"}}
        result = await client.post("/api/v1/auth/phone/continue", json={**body, "current_password": PASSWORD})
        assert result.status_code == 200 and result.json()["signup_grant_credits"] == 0
        assert all(response.headers["cache-control"] == "no-store" for response in (required, wrong, result))
        assert PHONE not in str(required.json()) and "mask" not in str(required.json())
    assert PASSWORD not in caplog.text and "private-wrong" not in caplog.text and values["code"] not in caplog.text
    with sessions() as db:
        assert db.query(models_db.PhoneIdentity).one().user_id == user_id


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["current_password", "new_password"])
async def test_new_password_fields_have_redacted_validation(phone_app, field):
    app, _, _ = phone_app
    route = "continue" if field == "current_password" else "password"
    body = {"challenge_id": "a" * 48, "flow_id": FLOW, "code": "123456", field: {"secret": "never-echo-this"}}
    if route == "continue":
        body["public_username"] = "棋手"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        result = await client.post(f"/api/v1/auth/phone/{route}", json=body)
        # Supply an eligible actor so password route reaches body validation.
        if result.status_code == 401:
            with phone_app[2]() as db, db.begin():
                db.add(models_db.User(username="actor", hashed_password="test-only"))
            result = await client.post(
                f"/api/v1/auth/phone/{route}",
                json=body,
                headers={"Authorization": f"Bearer {create_access_token(data={'sub': 'actor'})}"},
            )
        assert result.status_code == 400 and result.json() == {"detail": {"code": "invalid_password"}}
        assert result.headers["cache-control"] == "no-store" and "never-echo-this" not in result.text


@pytest.mark.asyncio
async def test_password_requires_authenticated_nonguest_actor(phone_app):
    app, _, sessions = phone_app
    with sessions() as db, db.begin():
        db.add(models_db.User(username="guest", hashed_password="test-only"))
    body = {"challenge_id": "a" * 48, "flow_id": FLOW, "code": "123456", "new_password": NEW_PASSWORD}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        anonymous = await client.post("/api/v1/auth/phone/password", json=body)
        assert anonymous.status_code == 401 and anonymous.json() == {"detail": {"code": "authentication_required"}}
        guest = await client.post(
            "/api/v1/auth/phone/password",
            json=body,
            headers={"Authorization": f"Bearer {create_access_token(data={'sub': 'guest'})}"},
        )
        assert guest.status_code == 403 and guest.json() == {"detail": {"code": "bind_not_allowed"}}


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["password_required", "invalid_grant", "success"])
async def test_board_continuation_uses_cloud_authority_and_validates_before_install(phone_app, outcome):
    app, _, sessions = phone_app
    seen = []

    async def handle(request):
        seen.append(request)
        if request.url.path.endswith("/phone/continue"):
            if outcome == "password_required":
                return httpx.Response(
                    409,
                    json={
                        "detail": {
                            "code": "account_password_required",
                            "phone": "private",
                            "masked_phone": "private",
                            "message": "private",
                        }
                    },
                )
            return httpx.Response(
                200,
                json={
                    "access_token": "candidate",
                    "signup_grant_credits": True if outcome == "invalid_grant" else 5000,
                },
            )
        assert request.url.path == "/api/v1/auth/me" and request.headers["authorization"] == "Bearer candidate"
        return httpx.Response(200, json={"id": 777, "username": "u_" + "a" * 20, "public_username": "云端棋手"})

    remote = await client_with_handler(handle)
    app.state.remote_client = remote
    remote.set_tokens("installed-a", user_id=7)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/phone/continue",
                json={"challenge_id": "a" * 48, "flow_id": FLOW, "code": "123456", "public_username": "云端棋手"},
            )
        assert response.headers["cache-control"] == "no-store"
        if outcome == "success":
            assert response.status_code == 200 and response.json()["signup_grant_credits"] == 5000
            with sessions() as db:
                shadow = db.query(models_db.User).one()
                assert shadow.public_username == "云端棋手" and shadow.hashed_password == "SHADOW_USER_NO_LOCAL_AUTH"
                assert remote.cloud_session_is(shadow.id)
            assert remote._access_token == "candidate"
        else:
            expected = "account_password_required" if outcome == "password_required" else "sms_unavailable"
            assert response.status_code == (409 if outcome == "password_required" else 503)
            assert response.json() == {"detail": {"code": expected}}
            assert remote.cloud_session_is(7) and remote._access_token == "installed-a"
            with sessions() as db:
                assert db.query(models_db.User).count() == 0
        assert len(seen) == (1 if outcome == "password_required" else 2)
    finally:
        await remote.close()


@pytest.mark.asyncio
async def test_board_password_forwards_204_and_keeps_existing_shadow_identity(phone_app, monkeypatch):
    from katrain.web.api.v1.endpoints import phone_auth

    app, _, sessions = phone_app
    with sessions() as db, db.begin():
        user = models_db.User(username="u_" + "a" * 20, hashed_password="SHADOW_USER_NO_LOCAL_AUTH")
        db.add(user)
        db.flush()
        user_id, user_uuid = user.id, user.uuid
    seen = []

    async def handle(request):
        seen.append(request)
        assert request.url.path == "/api/v1/auth/phone/password"
        assert request.headers["authorization"] == "Bearer installed-a"
        return httpx.Response(204)

    def forbidden(request):
        pytest.fail("phone authority must remain in cloud, never local shadows")

    monkeypatch.setattr(phone_auth, "get_phone_otp_service", forbidden)
    remote = await client_with_handler(handle)
    app.state.remote_client = remote
    remote.set_tokens("installed-a", user_id=user_id)
    generation = remote._identity_generation
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/phone/password",
                json={"challenge_id": "a" * 48, "flow_id": FLOW, "code": "123456", "new_password": NEW_PASSWORD},
                headers={"Authorization": f"Bearer {create_access_token({'sub': 'u_' + 'a' * 20})}"},
            )
        assert response.status_code == 204 and response.content == b""
        assert remote._identity_generation == generation and remote.cloud_session_is(user_id)
        assert len(seen) == 1 and remote._access_token == "installed-a"
        with sessions() as db:
            user = db.get(models_db.User, user_id)
            assert user.uuid == user_uuid and user.hashed_password == "SHADOW_USER_NO_LOCAL_AUTH"
    finally:
        await remote.close()
