"""Phase 2: billing REST API — auth boundaries, redeem flow, admin grant.

Uses an isolated SQLite DB via a get_db dependency override so the endpoints and
the auth repo share the same database.
"""

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.core.db import Base, get_db

settings.DATABASE_URL = "sqlite:///./test_billing_api.db"


@pytest.fixture
def app():
    settings.KATRAIN_MODE = "server"
    if os.path.exists("./test_billing_api.db"):
        os.remove("./test_billing_api.db")

    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.server import create_app

    test_engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    app = create_app(enable_engine=False)
    app.state.user_repo = SQLAlchemyUserRepository(TestSessionLocal)

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    app.state._TestSessionLocal = TestSessionLocal

    yield app

    if os.path.exists("./test_billing_api.db"):
        os.remove("./test_billing_api.db")


async def _make_user(app, username, password="pw", is_admin=False, credits=10000):
    from passlib.context import CryptContext
    from katrain.web.core import models_db

    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    app.state.user_repo.create_user(username, pwd.hash(password))
    s = app.state._TestSessionLocal()
    try:
        u = s.query(models_db.User).filter_by(username=username).one()
        u.is_admin = is_admin
        u.credits = credits
        s.commit()
    finally:
        s.close()


async def _login(ac, username, password="pw"):
    r = await ac.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
async def test_balance_and_prices(app):
    await _make_user(app, "alice", credits=500)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        h = await _login(ac, "alice")
        r = await ac.get("/api/v1/billing/balance", headers=h)
        assert r.status_code == 200 and r.json()["credits"] == 500
        r = await ac.get("/api/v1/billing/prices", headers=h)
        assert "territory" in r.json()["prices"]


@pytest.mark.asyncio
async def test_balance_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/v1/billing/balance")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_non_admin_cannot_grant_or_make_codes(app):
    await _make_user(app, "bob", is_admin=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        h = await _login(ac, "bob")
        r = await ac.post("/api/v1/billing/admin/grant", json={"username": "bob", "amount": 100}, headers=h)
        assert r.status_code == 403
        r = await ac.post("/api/v1/billing/admin/codes", json={"count": 1, "credits": 100}, headers=h)
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_grant_increases_balance(app):
    await _make_user(app, "boss", is_admin=True)
    await _make_user(app, "carol", credits=0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        h = await _login(ac, "boss")
        r = await ac.post("/api/v1/billing/admin/grant", json={"username": "carol", "amount": 250}, headers=h)
        assert r.status_code == 200 and r.json()["credits"] == 250


@pytest.mark.asyncio
async def test_redeem_flow(app):
    await _make_user(app, "boss", is_admin=True)
    await _make_user(app, "dave", credits=0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ah = await _login(ac, "boss")
        r = await ac.post("/api/v1/billing/admin/codes", json={"count": 1, "credits": 300}, headers=ah)
        code = r.json()["codes"][0]

        dh = await _login(ac, "dave")
        r = await ac.post("/api/v1/billing/redeem", json={"code": code}, headers=dh)
        assert r.status_code == 200 and r.json()["credits"] == 300
        # second redeem of same code fails (indistinguishable error)
        r = await ac.post("/api/v1/billing/redeem", json={"code": code}, headers=dh)
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_board_mode_balance_needs_online(app):
    await _make_user(app, "kioskuser", credits=500)
    settings.KATRAIN_MODE = "board"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            h = await _login(ac, "kioskuser")
            r = await ac.get("/api/v1/billing/balance", headers=h)
            assert r.status_code == 503
            assert r.json()["detail"]["code"] == "need_online_billing"
    finally:
        settings.KATRAIN_MODE = "server"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
