"""Frozen membership HTTP contracts, ownership, mode and remote-only boundaries."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import sessionmaker

from tests.web_ui.membership_test_support import membership_pg_engine
from katrain.web.core import models_db as m
from katrain.web.core.config import settings
from katrain.web.core.db import get_db
from katrain.web.api.v1.endpoints.auth import get_current_user, require_writable_user


@pytest.fixture
def api(membership_pg_engine, monkeypatch):
    from katrain.web.api.v1.endpoints import billing

    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "enabled")
    monkeypatch.setattr(settings, "PAYMENTS_MODE", "disabled")
    monkeypatch.setattr(settings, "KATRAIN_ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    Session = sessionmaker(bind=membership_pg_engine, expire_on_commit=False, autoflush=False)
    with Session.begin() as db:
        user = m.User(username="api-buyer", hashed_password="x", credits=1000)
        other = m.User(username="other-buyer", hashed_password="x", credits=0)
        db.add_all([user, other])
        db.flush()
        uid, otherid = user.id, other.id
        db.add(m.UserGame(id="mine", user_id=uid, sgf_content="(;SZ[19];B[aa];W[bb])", source="import"))
        db.add(m.UserGame(id="theirs", user_id=otherid, sgf_content="(;SZ[19];B[aa])", source="import"))
    app = FastAPI()
    app.include_router(billing.router, prefix="/api/v1/billing")

    def db_dependency():
        with Session() as db:
            yield db

    identity = SimpleNamespace(id=uid, username="api-buyer", uuid="cloud-owner", is_admin=False)
    app.dependency_overrides[get_db] = db_dependency
    app.dependency_overrides[get_current_user] = lambda: identity
    app.dependency_overrides[require_writable_user] = lambda: identity
    app.state.test_session = Session
    app.state.identity = identity
    return app


@pytest.mark.asyncio
async def test_usage_and_catalog_have_frozen_shapes_and_no_store(api):
    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as ac:
        usage = await ac.get("/api/v1/billing/usage")
        catalog = await ac.get("/api/v1/billing/catalog")
    assert usage.status_code == catalog.status_code == 200
    assert usage.headers["cache-control"] == catalog.headers["cache-control"] == "no-store"
    data = usage.json()
    assert data["wallet"] == {"credits": 1000, "display_points": "10.00"}
    assert data["plan"] == {"current": None, "next": None}
    assert data["free"]["eligible"] is False and isinstance(data["free"]["reason"], str)
    assert catalog.json()["profiles"]["advanced"] == {
        "visits": 2000,
        "credits_per_position": 4,
        "display_points_per_position": "0.04",
    }
    assert next(p for p in catalog.json()["plans"] if p["code"] == "max")["sale_enabled"] is False
    assert {p["code"]: p["full_use_savings_percent"] for p in catalog.json()["plans"]} == {
        "plus": 56.8,
        "pro": 63.5,
        "max": 72.5,
    }
    assert data["capabilities"]["orders"] is False


@pytest.mark.asyncio
async def test_quote_recomputes_n_plus_one_and_checks_owned_game(api):
    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as ac:
        quote = await ac.post(
            "/api/v1/billing/quotes", json={"kind": "report", "profile": "advanced", "game_id": "mine"}
        )
        wrong = await ac.post(
            "/api/v1/billing/quotes", json={"kind": "report", "profile": "normal", "game_id": "theirs"}
        )
        forged = await ac.post(
            "/api/v1/billing/quotes", json={"kind": "report", "profile": "normal", "game_id": "mine", "units": 1}
        )
    assert quote.status_code == 200, quote.text
    assert quote.json()["units"] == quote.json()["wallet_max_credits"] == 12
    assert quote.json()["source_policy"] == "membership_then_wallet"
    assert wrong.status_code == 404
    assert forged.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["legacy", "paused"])
async def test_disabled_membership_keeps_usage_readable_but_refuses_new_quotes(api, monkeypatch, mode):
    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", mode)
    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as ac:
        usage = await ac.get("/api/v1/billing/usage")
        quote = await ac.post(
            "/api/v1/billing/quotes", json={"kind": "position", "profile": "normal", "sgf": "(;SZ[19])"}
        )
    assert usage.status_code == 200
    assert usage.json()["capabilities"]["quotes"] is False
    assert usage.json()["capabilities"]["orders"] is False
    assert quote.status_code == 503


@pytest.mark.asyncio
async def test_board_uses_bound_cloud_identity_and_never_local_usage(api, monkeypatch):
    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    calls = []

    class Cloud:
        async def billing_usage(self, *, expected_user_id):
            calls.append(expected_user_id)
            return {"wallet": None, "authority": "cloud"}

    api.state.repository_dispatcher = Cloud()
    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as ac:
        result = await ac.get("/api/v1/billing/usage")
        del api.state.repository_dispatcher
        offline = await ac.get("/api/v1/billing/usage")
    assert result.status_code == 200 and result.json()["wallet"] is None
    assert calls == [api.state.identity.id]
    assert offline.status_code == 503


@pytest.mark.asyncio
async def test_checkout_is_server_priced_idempotent_and_receipts_are_owned(api, monkeypatch):
    import os

    monkeypatch.setenv("KATRAIN_DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setattr(settings, "PAYMENTS_MODE", "mock")
    monkeypatch.setattr(settings, "PAYMENT_MOCK_EVENT_SECRET", "test-admin-event-key")
    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as ac:
        data = {"sku": "membership_plus", "provider": "mock", "idempotency_key": "http-buy"}
        first = await ac.post("/api/v1/billing/orders", json=data)
        replay = await ac.post("/api/v1/billing/orders", json=data)
        conflict = await ac.post("/api/v1/billing/orders", json={**data, "sku": "membership_pro"})
        maxplan = await ac.post(
            "/api/v1/billing/orders", json={**data, "sku": "membership_max", "idempotency_key": "max"}
        )
        forged = await ac.post("/api/v1/billing/orders", json={**data, "amount_fen": 1})
        assert first.status_code == replay.status_code == 200
        assert first.json()["id"] == replay.json()["id"]
        assert first.json()["amount_fen"] == 3900 and first.json()["payment_url"] is None
        assert first.json()["fulfillment"] is None and first.json()["estimated_starts_at"]
        assert conflict.status_code == 409 and maxplan.status_code == 422 and forged.status_code == 422
        oid = first.json()["id"]
        mine = await ac.get("/api/v1/billing/orders")
        assert [r["id"] for r in mine.json()["orders"]] == [oid]
        api.state.identity.id += 1
        hidden = await ac.get(f"/api/v1/billing/orders/{oid}")
        otherlist = await ac.get("/api/v1/billing/orders")
        assert hidden.status_code == 404 and otherlist.json() == {"orders": []}


@pytest.mark.asyncio
async def test_sensitive_api_errors_also_disable_caching(api):
    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as ac:
        invalid = await ac.post("/api/v1/billing/quotes", json={"kind": "report", "profile": "invalid"})
        assert invalid.status_code == 422
        assert invalid.headers.get("cache-control") == "no-store"


@pytest.mark.asyncio
async def test_pending_ranked_game_blocks_sessionless_quote_before_analysis_input(api):
    api.state.ai_ladder_repo = SimpleNamespace(get_pending_game=lambda user_id: {"id": "pending-ranked"})
    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as ac:
        quote = await ac.post(
            "/api/v1/billing/quotes", json={"kind": "position", "profile": "normal", "sgf": "invalid-sgf"}
        )
    assert quote.status_code == 403
