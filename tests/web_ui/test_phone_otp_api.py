"""Private OTP HTTP contract, canonical token minting and registration bypass closure."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DBAPIError

from katrain.web.api.v1.api import api_router
from katrain.web.core import models_db
from katrain.web.core.auth import SQLAlchemyUserRepository
from katrain.web.core.auth import create_access_token
from katrain.web.core.config import settings
from jose import jwt
from katrain.web.core.remote_client import RemoteAPIClient


@pytest.fixture
def app(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'phone-api.db'}", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(engine)
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.state.user_repo = SQLAlchemyUserRepository(sessionmaker(bind=engine))
    yield app
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("board", [False, True])
async def test_legacy_unverified_register_is_closed_without_creating_account(app, board):
    remote = SimpleNamespace(register=AsyncMock(return_value={"username": "unverified"}))
    if board:
        app.state.remote_client = remote
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/register", json={"username": "unverified", "password": "password"})
    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "phone_verification_required"}}
    assert app.state.user_repo.get_user_by_username("unverified") is None
    remote.register.assert_not_awaited()


@pytest.mark.asyncio
async def test_phone_challenge_route_exists_and_invalid_input_is_private(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/phone/challenges", json={"phone": "not-a-phone", "purpose": "login", "flow_id": "f" * 32}
        )
    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "invalid_phone"}}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_challenge_uses_peer_and_never_forwarded_headers(app, monkeypatch):
    from katrain.web.api.v1.endpoints import phone_auth

    service = SimpleNamespace(
        request_challenge=AsyncMock(
            return_value={"challenge_id": "a" * 48, "retry_after": 60, "expires_in": 300, "delivery": "unknown"}
        )
    )
    monkeypatch.setattr(phone_auth, "get_phone_otp_service", lambda request: service)
    transport = httpx.ASGITransport(app=app, client=("192.0.2.21", 12000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/phone/challenges",
            json={"phone": "13800138000", "purpose": "login", "flow_id": "f" * 32},
            headers={"X-Forwarded-For": "203.0.113.19", "X-Real-IP": "203.0.113.22"},
        )
    assert response.status_code == 200 and response.json()["delivery"] == "unknown"
    service.request_challenge.assert_awaited_once_with(
        phone="13800138000", purpose="login", flow_id="f" * 32, client_ip="192.0.2.21", actor_id=None
    )
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_phone_login_mints_existing_canonical_token_contract(app, monkeypatch):
    from katrain.web.api.v1.endpoints import phone_auth
    from unittest.mock import Mock

    canonical = app.state.user_repo.create_user("u_1234567890abcdef1234", "hidden-hash")
    service = SimpleNamespace(login=Mock(return_value=canonical))
    monkeypatch.setattr(phone_auth, "get_phone_otp_service", lambda request: service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8081") as client:
        response = await client.post(
            "/api/v1/auth/phone/login", json={"challenge_id": "a" * 48, "code": "123456", "flow_id": "f" * 32}
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert claims["sub"] == canonical["username"] and claims["type"] == "access"
        assert "sb_token=" in response.headers["set-cookie"]
        me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["id"] == canonical["id"]
    assert "phone" not in me.json() and "hashed_password" not in me.json()
    service.login.assert_called_once_with(challenge_id="a" * 48, code="123456", flow_id="f" * 32)


@pytest.mark.asyncio
async def test_phone_status_requires_auth_and_returns_only_private_mask(app, monkeypatch):
    from katrain.web.api.v1.endpoints import phone_auth
    from unittest.mock import Mock

    user = app.state.user_repo.create_user("legacy", "hidden-hash")
    service = SimpleNamespace(
        status=Mock(return_value={"bound": True, "masked_phone": "+86 138****8000", "phone_e164": "+8613800138000"})
    )
    monkeypatch.setattr(phone_auth, "get_phone_otp_service", lambda request: service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        denied = await client.get("/api/v1/auth/phone/status")
        response = await client.get(
            "/api/v1/auth/phone/status", headers={"Authorization": f"Bearer {create_access_token({'sub': 'legacy'})}"}
        )
    assert denied.status_code == 401 and denied.json() == {"detail": {"code": "authentication_required"}}
    assert response.status_code == 200 and response.json() == {"bound": True, "masked_phone": "+86 138****8000"}
    service.status.assert_called_once_with(user_id=user["id"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"challenge_id": "a" * 48, "code": "sensitive-code", "flow_id": "f" * 32},
        {"challenge_id": "a" * 48, "code": 123456, "flow_id": "f" * 32},
        {"challenge_id": "a" * 48, "code": "１２３４５６", "flow_id": "f" * 32},
    ],
)
async def test_invalid_code_errors_never_echo_private_input(app, payload):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/phone/login", json=payload)
    assert response.status_code == 400 and response.json() == {"detail": {"code": "invalid_code"}}


@pytest.mark.asyncio
async def test_service_limit_error_keeps_structured_retry_and_no_store(app, monkeypatch):
    from katrain.web.api.v1.endpoints import phone_auth
    from katrain.web.core.phone_otp import PhoneOtpError

    service = SimpleNamespace(request_challenge=AsyncMock(side_effect=PhoneOtpError("sms_limited", 429, 51)))
    monkeypatch.setattr(phone_auth, "get_phone_otp_service", lambda request: service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/phone/challenges", json={"phone": "13800138000", "purpose": "login", "flow_id": "f" * 32}
        )
    assert response.status_code == 429 and response.json() == {"detail": {"code": "sms_limited", "retry_after": 51}}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_database_error_is_contained_without_private_response_log_or_exception(app, monkeypatch, caplog):
    import traceback
    from katrain.web.api.v1.endpoints import phone_auth

    private_phone, private_code = "+8613800138000", "314159"
    error = DBAPIError(
        "INSERT INTO private_phone_table VALUES (:phone, :code)",
        {"phone": private_phone, "code": private_code},
        RuntimeError(f"database rejected private values {private_phone} {private_code}"),
    )
    service = SimpleNamespace(request_challenge=AsyncMock(side_effect=error))
    monkeypatch.setattr(phone_auth, "get_phone_otp_service", lambda request: service)
    # Default ASGITransport raises uncaught application errors. Receiving this
    # response proves the original DBAPIError never reaches server middleware.
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/phone/challenges", json={"phone": private_phone, "purpose": "login", "flow_id": "f" * 32}
        )
    assert response.status_code == 503 and response.json() == {"detail": {"code": "sms_unavailable"}}
    assert response.headers["cache-control"] == "no-store"
    diagnostic = response.text + caplog.text
    diagnostic += "".join(
        "".join(traceback.format_exception(*record.exc_info)) for record in caplog.records if record.exc_info
    )
    assert private_phone not in diagnostic and private_code not in diagnostic


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["login", "register"])
async def test_board_phone_login_keeps_candidate_private_until_canonical_confirmation(app, monkeypatch, operation):
    entered, release = asyncio.Event(), asyncio.Event()
    saved = []
    monkeypatch.setattr("katrain.web.core.credentials.save_refresh_token", lambda *args: saved.append(args))

    async def handle(request):
        if request.url.path.endswith(f"/phone/{operation}"):
            return httpx.Response(
                200, json={"access_token": "candidate-a", "refresh_token": "refresh-a", "signup_grant_credits": 5000}
            )
        assert request.url.path == "/api/v1/auth/me" and request.headers["authorization"] == "Bearer candidate-a"
        entered.set()
        await release.wait()
        return httpx.Response(200, json={"username": "u_canonical_cloud", "public_username": "远端棋手", "id": 88})

    remote = RemoteAPIClient("http://cloud.test", "phone-box")
    await remote._client.aclose()
    remote._client = httpx.AsyncClient(base_url="http://cloud.test", transport=httpx.MockTransport(handle))
    app.state.remote_client = remote
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            pending = asyncio.create_task(
                client.post(
                    f"/api/v1/auth/phone/{operation}",
                    json={
                        "challenge_id": "a" * 48,
                        "code": "123456",
                        "flow_id": "f" * 32,
                        **(
                            {"public_username": "远端棋手", "password": "private-long-password"}
                            if operation == "register"
                            else {}
                        ),
                    },
                )
            )
            await asyncio.wait_for(entered.wait(), 2)
            assert not remote.is_authenticated and saved == []
            assert app.state.user_repo.get_user_by_username("u_canonical_cloud") is None
            release.set()
            response = await pending
        assert response.status_code == 200
        claims = jwt.decode(response.json()["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert claims["sub"] == "u_canonical_cloud"
        local = app.state.user_repo.get_user_by_username("u_canonical_cloud")
        assert local["public_username"] == "远端棋手"
        assert remote.cloud_session_is(local["id"]) and len(saved) == 1
        if operation == "register":
            assert response.json()["signup_grant_credits"] == 5000
    finally:
        release.set()
        await remote.close()


@pytest.mark.asyncio
async def test_late_board_password_login_never_creates_or_saves_old_identity(app, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    saved = []
    monkeypatch.setattr("katrain.web.core.credentials.save_refresh_token", lambda *args: saved.append(args))

    async def handle(request):
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json={"access_token": "candidate-a", "refresh_token": "refresh-a"})
        entered.set()
        await release.wait()
        return httpx.Response(200, json={"username": "account-a"})

    remote = RemoteAPIClient("http://cloud.test", "phone-box")
    await remote._client.aclose()
    remote._client = httpx.AsyncClient(base_url="http://cloud.test", transport=httpx.MockTransport(handle))
    app.state.remote_client = remote
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            pending = asyncio.create_task(
                client.post("/api/v1/auth/login", json={"username": "account-a", "password": "private-password"})
            )
            await asyncio.wait_for(entered.wait(), 2)
            remote.set_tokens("token-b", "refresh-b", user_id=8)
            release.set()
            response = await pending
        assert response.status_code == 409 and response.json() == {"detail": {"code": "identity_changed"}}
        assert app.state.user_repo.get_user_by_username("account-a") is None and saved == []
        assert remote.cloud_session_is(8) and remote._access_token == "token-b"
    finally:
        release.set()
        await remote.close()


@pytest.mark.asyncio
async def test_malformed_cloud_me_does_not_install_password_candidate(app, monkeypatch):
    saved = []
    monkeypatch.setattr("katrain.web.core.credentials.save_refresh_token", lambda *args: saved.append(args))

    async def handle(request):
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json={"access_token": "candidate-a", "refresh_token": "refresh-a"})
        return httpx.Response(200, json={"username": None})

    remote = RemoteAPIClient("http://cloud.test", "phone-box")
    await remote._client.aclose()
    remote._client = httpx.AsyncClient(base_url="http://cloud.test", transport=httpx.MockTransport(handle))
    app.state.remote_client = remote
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/login", json={"username": "alias", "password": "private-password"}
            )
        assert response.status_code == 503
        assert not remote.is_authenticated and saved == []
    finally:
        await remote.close()


@pytest.mark.asyncio
async def test_slow_logout_invalidates_candidates_immediately_and_preserves_new_login(app, monkeypatch):
    from katrain.web.session import LobbyManager, Matchmaker, SessionManager

    entered, release = asyncio.Event(), asyncio.Event()
    monkeypatch.setattr("katrain.web.core.credentials.delete_credentials", lambda *_: None)
    user = app.state.user_repo.create_user("account-a", "hidden-hash")
    app.state.lobby_manager = LobbyManager()
    app.state.matchmaker = Matchmaker()
    app.state.session_manager = SessionManager(enable_engine=False)

    async def release_platform(_user_id):
        entered.set()
        await release.wait()

    app.state.platform_manager = SimpleNamespace(release_user=release_platform)
    remote = RemoteAPIClient("http://cloud.test", "phone-box")
    remote.set_tokens("token-a", "refresh-a", user_id=user["id"])
    app.state.remote_client = remote
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            pending = asyncio.create_task(
                client.post(
                    "/api/v1/auth/logout",
                    headers={"Authorization": f"Bearer {create_access_token({'sub': 'account-a'})}"},
                )
            )
            await asyncio.wait_for(entered.wait(), 2)
            assert not remote.is_authenticated
            remote.set_tokens("token-b", "refresh-b", user_id=8)
            release.set()
            response = await pending
        assert response.status_code == 200 and remote.cloud_session_is(8)
    finally:
        release.set()
        await remote.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,payload,expected",
    [
        ("challenges", {"phone": {"secret": "do-not-echo"}, "purpose": "login", "flow_id": "f" * 32}, "invalid_phone"),
        ("challenges", {"phone": "1" * 1000, "purpose": "login", "flow_id": "f" * 32}, "invalid_phone"),
        ("challenges", {"phone": "13800138000", "purpose": "login", "flow_id": "short"}, "challenge_invalid"),
        (
            "login",
            {"challenge_id": "a" * 48, "code": "123456", "flow_id": "f" * 32, "current_password": "do-not-echo"},
            "challenge_invalid",
        ),
    ],
)
async def test_phone_body_validation_never_echoes_private_fields(app, path, payload, expected):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/auth/phone/{path}", json=payload)
    assert response.status_code == 400 and response.json() == {"detail": {"code": expected}}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_board_provider_error_drops_arbitrary_messages_and_fields(app):
    async def handle(request):
        return httpx.Response(
            503,
            json={
                "detail": {
                    "code": "sms_rejected",
                    "retry_after": 60,
                    "message": "do-not-echo",
                    "phone": "+8613800138000",
                }
            },
        )

    remote = RemoteAPIClient("http://cloud.test", "phone-box")
    await remote._client.aclose()
    remote._client = httpx.AsyncClient(base_url="http://cloud.test", transport=httpx.MockTransport(handle))
    app.state.remote_client = remote
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/phone/challenges", json={"phone": "13800138000", "purpose": "login", "flow_id": "f" * 32}
            )
        assert response.status_code == 503 and response.json() == {
            "detail": {"code": "sms_rejected", "retry_after": 60}
        }
    finally:
        await remote.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "password_payload", [{}, {"current_password": ""}, {"current_password": "wrong-private-password"}]
)
async def test_bind_missing_empty_and_wrong_password_reach_core_reauth_budget(app, monkeypatch, password_payload):
    from unittest.mock import Mock
    from katrain.web.api.v1.endpoints import phone_auth
    from katrain.web.core.phone_otp import PhoneOtpError

    user = app.state.user_repo.create_user("legacy-bind", "hidden-hash")
    service = SimpleNamespace(bind=Mock(side_effect=PhoneOtpError("bind_reauth_failed", 401)))
    monkeypatch.setattr(phone_auth, "get_phone_otp_service", lambda request: service)
    payload = {"challenge_id": "a" * 48, "code": "123456", "flow_id": "f" * 32, **password_payload}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/phone/bind",
            json=payload,
            headers={"Authorization": f"Bearer {create_access_token({'sub': user['username']})}"},
        )
    assert response.status_code == 401 and response.json() == {"detail": {"code": "bind_reauth_failed"}}
    assert response.headers["cache-control"] == "no-store"
    service.bind.assert_called_once_with(
        user_id=user["id"],
        challenge_id="a" * 48,
        code="123456",
        flow_id="f" * 32,
        current_password=password_payload.get("current_password"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("username,is_admin", [("guest", False), ("admin", False), ("ordinary-admin", True)])
async def test_bind_rejects_guest_and_admin_before_service(app, monkeypatch, username, is_admin):
    from unittest.mock import Mock
    from katrain.web.api.v1.endpoints import phone_auth

    user = app.state.user_repo.create_user(username, "hidden-hash")
    if is_admin:
        with app.state.user_repo.session_factory() as db:
            db.get(models_db.User, user["id"]).is_admin = True
            db.commit()
    factory = Mock()
    monkeypatch.setattr(phone_auth, "get_phone_otp_service", factory)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/phone/bind",
            json={
                "challenge_id": "a" * 48,
                "code": "123456",
                "flow_id": "f" * 32,
                "current_password": "private-password",
            },
            headers={"Authorization": f"Bearer {create_access_token({'sub': username})}"},
        )
    assert response.status_code == 403 and response.json() == {"detail": {"code": "bind_not_allowed"}}
    factory.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extra", [{"current_password": 123456}, {"current_password": "private-value-" * 100}, {"user_id": 999}]
)
async def test_bind_strict_password_limits_and_server_owned_user_id_do_not_echo_input(app, monkeypatch, extra):
    from unittest.mock import Mock
    from katrain.web.api.v1.endpoints import phone_auth

    user = app.state.user_repo.create_user("bind-validator", "hidden-hash")
    factory = Mock()
    monkeypatch.setattr(phone_auth, "get_phone_otp_service", factory)
    payload = {
        "challenge_id": "a" * 48,
        "code": "123456",
        "flow_id": "f" * 32,
        "current_password": "private-password",
        **extra,
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/phone/bind",
            json=payload,
            headers={"Authorization": f"Bearer {create_access_token({'sub': user['username']})}"},
        )
    assert response.status_code == 400 and response.json() == {"detail": {"code": "challenge_invalid"}}
    assert response.headers["cache-control"] == "no-store"
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_board_bind_late_result_is_discarded_without_using_new_bearer(app):
    entered, release = asyncio.Event(), asyncio.Event()
    seen = []
    user = app.state.user_repo.create_user("legacy-a", "hidden-hash")

    async def handle(request):
        seen.append(request)
        entered.set()
        await release.wait()
        return httpx.Response(200, json={"bound": True, "masked_phone": "+86 138****8000"})

    remote = RemoteAPIClient("http://cloud.test", "bind-box")
    await remote._client.aclose()
    remote._client = httpx.AsyncClient(base_url="http://cloud.test", transport=httpx.MockTransport(handle))
    remote.set_tokens("token-a", "refresh-a", user_id=user["id"])
    app.state.remote_client = remote
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            pending = asyncio.create_task(
                client.post(
                    "/api/v1/auth/phone/bind",
                    json={
                        "challenge_id": "a" * 48,
                        "code": "123456",
                        "flow_id": "f" * 32,
                        "current_password": "private-password",
                    },
                    headers={"Authorization": f"Bearer {create_access_token({'sub': user['username']})}"},
                )
            )
            await asyncio.wait_for(entered.wait(), 2)
            remote.set_tokens("token-b", "refresh-b", user_id=8)
            release.set()
            response = await pending
        assert response.status_code == 409 and response.json() == {"detail": {"code": "identity_changed"}}
        assert len(seen) == 1 and seen[0].headers["authorization"] == "Bearer token-a"
        assert not seen[0].url.query and seen[0].url.path == "/api/v1/auth/phone/bind"
        assert remote.cloud_session_is(8)
    finally:
        release.set()
        await remote.close()


@pytest.mark.asyncio
async def test_board_profile_required_preserves_mode_and_existing_session(app):
    seen = []

    async def handle(request):
        seen.append(request)
        return httpx.Response(
            409, json={"detail": {"code": "profile_required", "mode": "complete", "phone": "private"}}
        )

    remote = RemoteAPIClient("http://cloud.test", "phone-box")
    await remote._client.aclose()
    remote._client = httpx.AsyncClient(base_url="http://cloud.test", transport=httpx.MockTransport(handle))
    remote.set_tokens("old-a", "old-r", user_id=7)
    app.state.remote_client = remote
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/phone/login", json={"challenge_id": "a" * 48, "code": "123456", "flow_id": "f" * 32}
            )
        assert response.status_code == 409 and response.json() == {
            "detail": {"code": "profile_required", "mode": "complete"}
        }
        assert response.headers["cache-control"] == "no-store"
        assert len(seen) == 1 and remote.cloud_session_is(7)
        assert app.state.user_repo.get_user_by_username("u_canonical_cloud") is None
    finally:
        await remote.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,expected", [("public_username", "invalid_public_username"), ("password", "invalid_password")]
)
async def test_register_validation_never_echoes_password_or_name(app, field, expected):
    payload = {
        "challenge_id": "a" * 48,
        "code": "123456",
        "flow_id": "f" * 32,
        "public_username": "棋手",
        "password": "do-not-echo-secret-password",
    }
    payload[field] = {"private": "do-not-echo-secret"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/phone/register", json=payload)
    assert response.status_code == 400 and response.json() == {"detail": {"code": expected}}
    assert response.headers["cache-control"] == "no-store" and "do-not-echo" not in response.text
