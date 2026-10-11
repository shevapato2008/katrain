"""The Go provider trusts only a short-lived assertion from SmartBox admin."""

import json
import time

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.core.models_db import AdminAuditLog, SystemConfigDB


SERVICE_SECRET = "service-key-" * 4
SESSION_SECRET = "session-key-" * 4
PUBLIC_SECRET = "public-key-" * 4
PASSWORD_HASH = CryptContext(schemes=["bcrypt"]).hash("legacy-admin-password")


@pytest.fixture
def admin_environment(monkeypatch):
    monkeypatch.setenv("KATRAIN_MODE", "server")
    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", PASSWORD_HASH)
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", SESSION_SECRET)
    monkeypatch.setenv("KATRAIN_ADMIN_SERVICE_SECRET", SERVICE_SECRET)
    monkeypatch.setenv("KATRAIN_SECRET_KEY", PUBLIC_SECRET)
    monkeypatch.delenv("KATRAIN_ADMIN_PROVIDER_ONLY", raising=False)
    monkeypatch.delenv("KATRAIN_BUILD_SHA", raising=False)


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    AdminAuditLog.__table__.create(engine)
    SystemConfigDB.__table__.create(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture
def client(admin_environment, session_factory, tmp_path):
    from katrain.web.admin.app import create_admin_app

    return TestClient(create_admin_app(session_factory=session_factory, static_dir=tmp_path))


def service_token(*, key=SERVICE_SECRET, algorithm="HS256", **changes):
    now = time.time()
    claims = {
        "iss": "smartbox-admin",
        "aud": "katrain-admin-service",
        "type": "admin_service",
        "sub": "admin:fan",
        "env": "test",
        "iat": now - 1,
        "exp": now + 30,
        "jti": "request-123",
    }
    claims.update({name: value(now) if callable(value) else value for name, value in changes.items()})
    return jwt.encode({key: value for key, value in claims.items() if value is not None}, key, algorithm=algorithm)


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_service_assertion_returns_the_verified_admin_actor(client):
    response = client.get("/api/admin/auth/me", headers=bearer(service_token()))
    assert response.status_code == 200, response.text
    assert response.json() == {"username": "admin:fan", "env": "test"}
    assert client.get("/api/admin/performance", headers=bearer(service_token())).status_code == 200


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": None},
        {"iss": "katrain"},
        {"aud": None},
        {"aud": "smartbox-admin"},
        {"aud": ["katrain-admin-service"]},
        {"sub": None},
        {"sub": "player:fan"},
        {"type": None},
        {"type": "admin_session"},
        {"env": None},
        {"env": "prod"},
        {"env": "staging"},
        {"iat": None},
        {"iat": True},
        {"iat": "1"},
        {"iat": float("nan")},
        {"iat": float("inf")},
        {"iat": 10**1000},
        {"iat": lambda now: now + 20},
        {"iat": lambda now: now - 120},
        {"exp": None},
        {"exp": True},
        {"exp": "9999999999"},
        {"exp": float("nan")},
        {"exp": float("inf")},
        {"exp": 10**1000},
        {"exp": lambda now: now - 1},
        {"exp": lambda now: now + 120},
        {"iat": 2, "exp": 1},
        {"jti": None},
        {"jti": ""},
        {"jti": "   "},
        {"jti": True},
        {"jti": "x" * 129},
    ],
)
def test_service_assertion_requires_exact_identity_and_bounded_validity(client, changes):
    assert client.get("/api/admin/performance", headers=bearer(service_token(**changes))).status_code == 401


@pytest.mark.parametrize("key", [SESSION_SECRET, PUBLIC_SECRET, "wrong-key-" * 4])
def test_service_assertion_requires_the_dedicated_key(client, key):
    assert client.get("/api/admin/performance", headers=bearer(service_token(key=key))).status_code == 401


def test_service_assertion_only_accepts_hs256(client):
    assert client.get("/api/admin/performance", headers=bearer(service_token(algorithm="HS384"))).status_code == 401


def test_actor_headers_cannot_authorize_a_request(client):
    headers = {"X-Admin-Username": "admin:fan", "X-Admin-Actor": "admin:fan", "X-Request-ID": "request-123"}
    assert client.get("/api/admin/performance", headers=headers).status_code == 401
    headers.update(bearer(service_token(sub="player:fan")))
    assert client.get("/api/admin/performance", headers=headers).status_code == 401


@pytest.mark.parametrize("value", [None, ""])
def test_empty_service_key_disables_assertions_in_legacy_mode(admin_environment, monkeypatch, tmp_path, value):
    from katrain.web.admin.app import create_admin_app
    from katrain.web.admin.settings import check_startup

    if value is None:
        monkeypatch.delenv("KATRAIN_ADMIN_SERVICE_SECRET")
    else:
        monkeypatch.setenv("KATRAIN_ADMIN_SERVICE_SECRET", value)
    assert check_startup().service_secret == ""
    client = TestClient(create_admin_app(session_factory=object(), static_dir=tmp_path))
    assert client.get("/api/admin/performance", headers=bearer(service_token())).status_code == 401


@pytest.mark.parametrize("provider_only", [False, True])
@pytest.mark.parametrize("value", ["short", " x" * 24, SESSION_SECRET, PUBLIC_SECRET])
def test_invalid_optional_service_key_fails_startup(admin_environment, monkeypatch, provider_only, value):
    from katrain.web.admin.settings import check_startup

    monkeypatch.setenv("KATRAIN_ADMIN_PROVIDER_ONLY", "1" if provider_only else "0")
    monkeypatch.setenv("KATRAIN_ADMIN_SERVICE_SECRET", value)
    with pytest.raises(RuntimeError, match="KATRAIN_ADMIN_SERVICE_SECRET"):
        check_startup()


def test_service_key_cannot_use_the_public_default(admin_environment, monkeypatch):
    from katrain.web.admin.settings import check_startup
    from katrain.web.core.config import INSECURE_DEFAULT_SECRET_KEY

    monkeypatch.delenv("KATRAIN_SECRET_KEY")
    monkeypatch.setenv("KATRAIN_ADMIN_SERVICE_SECRET", INSECURE_DEFAULT_SECRET_KEY)
    with pytest.raises(RuntimeError, match="KATRAIN_ADMIN_SERVICE_SECRET"):
        check_startup()


def test_provider_only_starts_without_legacy_credentials(admin_environment, monkeypatch):
    from katrain.web.admin.settings import check_startup

    monkeypatch.setenv("KATRAIN_ADMIN_PROVIDER_ONLY", "1")
    monkeypatch.delenv("KATRAIN_ADMIN_PASSWORD_HASH")
    monkeypatch.delenv("KATRAIN_ADMIN_SESSION_SECRET")
    config = check_startup()
    assert config.provider_only is True
    assert config.password_hash == config.session_secret == ""
    assert config.service_secret == SERVICE_SECRET


@pytest.mark.parametrize(
    "name,value",
    [
        ("KATRAIN_MODE", "desktop"),
        ("KATRAIN_ADMIN_USERNAME", "fan"),
        ("KATRAIN_ADMIN_ENV", "staging"),
        ("KATRAIN_ADMIN_SERVICE_SECRET", ""),
        ("KATRAIN_ADMIN_SESSION_SECRET", "weak-optional-key"),
    ],
)
def test_provider_only_rejects_invalid_required_or_optional_config(admin_environment, monkeypatch, name, value):
    from katrain.web.admin.settings import check_startup

    monkeypatch.setenv("KATRAIN_ADMIN_PROVIDER_ONLY", "1")
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match=name):
        check_startup()


def test_provider_only_disables_legacy_auth_and_static_but_keeps_domain_routes(
    admin_environment, monkeypatch, session_factory, tmp_path
):
    from katrain.web.admin.app import create_admin_app
    from katrain.web.admin.session import create_session_token

    legacy_token = create_session_token("admin:fan", "test")
    legacy_app = create_admin_app(session_factory=session_factory, static_dir=tmp_path)
    (tmp_path / "admin.html").write_text("<html>legacy admin</html>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "main.js").write_text("console.log(1)", encoding="utf-8")
    monkeypatch.setenv("KATRAIN_ADMIN_PROVIDER_ONLY", "1")
    monkeypatch.delenv("KATRAIN_ADMIN_PASSWORD_HASH")
    monkeypatch.delenv("KATRAIN_ADMIN_SESSION_SECRET")
    app = create_admin_app(session_factory=session_factory, static_dir=tmp_path)
    client = TestClient(app)
    for path in ("/", "/assets/main.js", "/login", "/api/admin/auth/me"):
        assert client.get(path, headers=bearer(service_token())).status_code == 404
    for path in ("/api/admin/auth/login", "/api/admin/auth/logout"):
        assert client.post(path, json={"username": "admin:fan", "password": "legacy-admin-password"}).status_code == 404
    assert client.get("/api/admin/performance", headers=bearer(legacy_token)).status_code == 401
    assert client.get("/api/admin/performance", headers=bearer(service_token())).status_code == 200
    domain_routes = {
        route.path
        for route in legacy_app.routes
        if route.path.startswith("/api/") and not route.path.startswith("/api/admin/auth/")
    }
    assert domain_routes <= {route.path for route in app.routes}
    public_reads = [route for route in app.routes if route.path.startswith("/api/v1/tutorials")]
    assert public_reads and all(route.methods <= {"GET", "HEAD"} for route in public_reads)
    assert app.state.vision_runtime is not None and app.state.vision_training is not None


@pytest.mark.parametrize("build", [None, "", "abc1234"])
def test_health_announces_the_owner_contract_and_honest_build(client, monkeypatch, build):
    from katrain.web.admin.app import create_admin_app

    if build is not None:
        monkeypatch.setenv("KATRAIN_BUILD_SHA", build)
    app = create_admin_app(session_factory=client.app.state.session_factory)
    assert TestClient(app).get("/api/admin/health").json() == {
        "status": "ok",
        "owner": "katrain",
        "env": "test",
        "admin_contract": 1,
        "build": build or "unknown",
    }


def test_provider_health_requires_service_authentication(admin_environment, monkeypatch, session_factory):
    from katrain.web.admin.app import create_admin_app
    from katrain.web.admin.session import create_session_token

    legacy_token = create_session_token("admin:fan", "test")
    monkeypatch.setenv("KATRAIN_ADMIN_PROVIDER_ONLY", "1")
    client = TestClient(create_admin_app(session_factory=session_factory))
    for headers in ({}, bearer(legacy_token), bearer(service_token(key=PUBLIC_SECRET))):
        assert client.get("/api/admin/health", headers=headers).status_code == 401
    response = client.get("/api/admin/health", headers=bearer(service_token()))
    assert response.status_code == 200
    assert response.json()["owner"] == "katrain"


def test_service_actor_is_used_for_a_real_atomic_bot_config_write(client, monkeypatch):
    headers = {**bearer(service_token()), "X-Admin-Username": "forged-actor"}
    config = {"version": 1, "enabled": False, "bot_game_limit": 3, "idle_targets": {}}
    response = client.put(
        "/api/admin/pvp-lobby/config", headers=headers, json={"expected_revision": 0, "config": config}
    )
    assert response.status_code == 200, response.text
    with client.app.state.session_factory() as db:
        saved = json.loads(db.get(SystemConfigDB, "pvp_lobby_bot_config").value)
        audit = db.scalar(select(AdminAuditLog))
        assert saved["revision"] == 1
        assert (audit.actor_realm, audit.actor_username, audit.action) == (
            "admin",
            "admin:fan",
            "pvp_lobby_config_update",
        )

    original_commit = Session.commit

    def fail_audit(session):
        if any(isinstance(row, AdminAuditLog) for row in session.new):
            raise RuntimeError("audit unavailable")
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        client.put(
            "/api/admin/pvp-lobby/config",
            headers=headers,
            json={"expected_revision": 1, "config": {**config, "enabled": True}},
        )
    with client.app.state.session_factory() as db:
        assert json.loads(db.get(SystemConfigDB, "pvp_lobby_bot_config").value)["revision"] == 1
        assert len(db.scalars(select(AdminAuditLog)).all()) == 1
