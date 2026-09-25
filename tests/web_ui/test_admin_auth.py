"""Dedicated admin identity never borrows a Galaxy account or session."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.core.auth import create_access_token, create_refresh_token
from katrain.web.core.models_db import AdminAuditLog


ADMIN_SECRET = "a" * 48
PUBLIC_SECRET = "p" * 48
PASSWORD = "admin-test-password"
PASSWORD_HASH = CryptContext(schemes=["bcrypt"]).hash(PASSWORD)


@pytest.fixture
def admin_config(monkeypatch):
    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", PASSWORD_HASH)
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", ADMIN_SECRET)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    monkeypatch.setenv("KATRAIN_SECRET_KEY", PUBLIC_SECRET)


@pytest.fixture
def audit_session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    AdminAuditLog.__table__.create(bind=engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture
def client(admin_config, tmp_path, audit_session_factory):
    from katrain.web.admin.app import create_admin_app

    return TestClient(create_admin_app(session_factory=audit_session_factory, static_dir=tmp_path))


def _audit_rows(client):
    with client.app.state.session_factory() as session:
        return session.scalars(select(AdminAuditLog).order_by(AdminAuditLog.id)).all()


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _claims(**overrides):
    claims = {
        "sub": "admin:fan",
        "type": "admin_session",
        "aud": "katrain-admin",
        "env": "test",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    claims.update(overrides)
    return {key: value for key, value in claims.items() if value is not None}


def test_admin_config_refuses_absent_or_weak_values(admin_config, monkeypatch):
    from katrain.web.admin.settings import check_startup

    for name, value in (
        ("KATRAIN_ADMIN_USERNAME", None),
        ("KATRAIN_ADMIN_USERNAME", "admin"),
        ("KATRAIN_ADMIN_PASSWORD_HASH", None),
        ("KATRAIN_ADMIN_PASSWORD_HASH", "plain-password"),
        ("KATRAIN_ADMIN_SESSION_SECRET", None),
        ("KATRAIN_ADMIN_SESSION_SECRET", "short"),
        ("KATRAIN_ADMIN_SESSION_SECRET", PUBLIC_SECRET),
        ("KATRAIN_ADMIN_ENV", None),
        ("KATRAIN_ADMIN_ENV", "staging"),
    ):
        with monkeypatch.context() as changed:
            if value is None:
                changed.delenv(name)
            else:
                changed.setenv(name, value)
            with pytest.raises(RuntimeError, match=name):
                check_startup()

    assert check_startup().env == "test"


def test_admin_config_refuses_the_public_default_secret(admin_config, monkeypatch):
    from katrain.web.admin.settings import check_startup
    from katrain.web.core.config import INSECURE_DEFAULT_SECRET_KEY

    monkeypatch.delenv("KATRAIN_SECRET_KEY")
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", INSECURE_DEFAULT_SECRET_KEY)
    with pytest.raises(RuntimeError, match="KATRAIN_ADMIN_SESSION_SECRET"):
        check_startup()


def test_login_me_logout_use_a_dedicated_identity_and_no_cookie(client):
    response = client.post("/api/admin/auth/login", json={"username": "admin:fan", "password": PASSWORD})
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    assert response.json()["token_type"] == "bearer"
    token = response.json()["access_token"]
    claims = jwt.decode(token, ADMIN_SECRET, algorithms=["HS256"], audience="katrain-admin")
    assert claims["sub"] == "admin:fan"
    assert claims["type"] == "admin_session"
    assert claims["aud"] == "katrain-admin"
    assert claims["env"] == "test"
    assert 7 * 3600 < claims["exp"] - datetime.now(timezone.utc).timestamp() <= 8 * 3600
    assert client.get("/api/admin/auth/me", headers=_bearer(token)).json() == {
        "username": "admin:fan",
        "env": "test",
    }
    assert client.post("/api/admin/auth/logout", headers=_bearer(token)).status_code == 204
    rows = _audit_rows(client)
    assert [(row.action, row.actor_realm, row.actor_username, row.success) for row in rows] == [
        ("login_success", "admin", "admin:fan", True),
        ("logout", "admin", "admin:fan", True),
    ]


def test_failed_logins_share_one_error(client):
    missing = client.post("/api/admin/auth/login", json={"username": "galaxy-user", "password": PASSWORD})
    wrong = client.post("/api/admin/auth/login", json={"username": "admin:fan", "password": "wrong"})
    assert missing.status_code == wrong.status_code == 401
    assert missing.json() == wrong.json()
    assert "password" not in str(missing.json()).lower()
    rows = _audit_rows(client)
    assert [(row.action, row.actor_realm, row.actor_username, row.success) for row in rows] == [
        ("login_failed", "admin", "galaxy-user", False),
        ("login_failed", "admin", "admin:fan", False),
    ]
    assert all(PASSWORD not in (row.detail or "") and "wrong" not in (row.detail or "") for row in rows)


def test_missing_audit_table_returns_503_before_login_or_logout(admin_config, tmp_path):
    from katrain.web.admin.app import create_admin_app
    from katrain.web.admin.session import create_session_token

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    factory = sessionmaker(bind=engine)
    try:
        broken = TestClient(create_admin_app(session_factory=factory, static_dir=tmp_path))
        for username, password in (("admin:fan", PASSWORD), ("nobody", "wrong")):
            response = broken.post("/api/admin/auth/login", json={"username": username, "password": password})
            assert response.status_code == 503
            assert response.json() == {"detail": "Admin audit unavailable"}
        token = create_session_token("admin:fan", "test")
        logout = broken.post("/api/admin/auth/logout", headers=_bearer(token))
        assert logout.status_code == 503
        assert logout.json() == {"detail": "Admin audit unavailable"}
    finally:
        engine.dispose()


def test_admin_me_requires_bearer(client):
    assert client.get("/api/admin/auth/me").status_code == 401
    assert client.get("/api/admin/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401


def test_public_access_and_refresh_tokens_cannot_enter_admin(client, monkeypatch):
    from katrain.web.core.config import settings as public_settings

    monkeypatch.setattr(public_settings, "SECRET_KEY", PUBLIC_SECRET)
    for token in (
        create_access_token({"sub": "admin:fan"}),
        create_refresh_token({"sub": "admin:fan"}),
    ):
        assert client.get("/api/admin/auth/me", headers=_bearer(token)).status_code == 401


@pytest.mark.parametrize(
    "changed",
    [
        {"sub": None},
        {"sub": "galaxy-user"},
        {"type": None},
        {"type": "access"},
        {"aud": None},
        {"aud": "katrain-web"},
        {"env": None},
        {"env": "prod"},
        {"exp": None},
        {"exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
    ],
)
def test_admin_token_requires_every_claim(client, changed):
    token = jwt.encode(_claims(**changed), ADMIN_SECRET, algorithm="HS256")
    assert client.get("/api/admin/auth/me", headers=_bearer(token)).status_code == 401


@pytest.mark.asyncio
async def test_admin_token_is_rejected_by_public_api_identity(admin_config, monkeypatch):
    from katrain.web.admin.session import create_session_token
    from katrain.web.api.v1.endpoints.auth import get_user_from_token
    from katrain.web.core.config import settings as public_settings

    class UserRepo:
        def get_user_by_username(self, username):
            pytest.fail("public user lookup must not happen for an admin token")

    token = create_session_token("admin:fan", "test")
    for public_key in (PUBLIC_SECRET, ADMIN_SECRET):
        monkeypatch.setattr(public_settings, "SECRET_KEY", public_key)
        with pytest.raises(HTTPException) as error:
            await get_user_from_token(token, UserRepo())
        assert error.value.status_code == 401


def test_admin_app_has_admin_routes_and_same_origin_tutorial_reads_and_static(client, tmp_path):
    from katrain.web.admin.app import CSP, NOT_BUILT, create_admin_app

    assert client.get("/api/admin/health").json() == {"status": "ok", "env": "test"}
    assert client.get("/").status_code == 503
    assert client.get("/").text == NOT_BUILT
    (tmp_path / "admin.html").write_text("<html>admin</html>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "main.js").write_text("console.log(1)", encoding="utf-8")
    built = TestClient(create_admin_app(static_dir=tmp_path))
    for path in ("/", "/assets/main.js", "/api/admin/health", "/api/admin/nope"):
        response = built.get(path)
        assert response.headers["content-security-policy"] == CSP
        assert "access-control-allow-origin" not in response.headers
    assert built.get("/").text == "<html>admin</html>"
    assert built.get("/assets/main.js").status_code == 200
    assert built.get("/api/admin/nope").status_code == 404
    tutorial_reads = [route for route in built.app.routes if route.path.startswith("/api/v1/tutorials")]
    assert tutorial_reads
    assert all(route.methods <= {"GET", "HEAD"} for route in tutorial_reads)
    assert not any(route.path.startswith("/api/v1/") and not route.path.startswith("/api/v1/tutorials") for route in built.app.routes)


def test_admin_app_keeps_injected_session_factory(admin_config, tmp_path):
    from katrain.web.admin.app import create_admin_app

    factory = object()
    app = create_admin_app(session_factory=factory, static_dir=tmp_path)
    assert app.state.session_factory is factory
