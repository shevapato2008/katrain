"""Short-analysis authorization uses the real isolated PostgreSQL ledger, never a GPU."""

from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from tests.web_ui.membership_test_support import membership_pg_engine
from katrain.web.core import models_db as m
from katrain.web.core.billing_catalog import MODEL_SHA256
from katrain.web.core.billing_input import canonical_analysis_input
from katrain.web.core import billing_operations as ops

SGF = "(;SZ[9]KM[7.5];B[aa];W[bb])"


def result(request_id, size=9, visits=500):
    return {
        "id": request_id,
        "turnNumber": 2,
        "isDuringSearch": False,
        "_wrapper": {"model_sha256": MODEL_SHA256, "model_sha256_verified": True, "selected_model": "paid"},
        "rootInfo": {"visits": visits, "winrate": 0.5, "scoreLead": 1.0},
        "moveInfos": [{"move": "C3", "visits": visits, "winrate": 0.5, "scoreLead": 1.0, "prior": 0.1, "pv": ["C3"]}],
        "ownership": [0.0] * (size * size),
    }


@pytest.fixture
def service(membership_pg_engine, monkeypatch):
    from katrain.web.api.v1.endpoints import paid_analysis
    from katrain.web.api.v1.endpoints.auth import require_writable_user, get_current_user
    from katrain.web.core.config import settings
    from katrain.web.core.db import get_db

    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "enabled")
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_ENVIRONMENT", "test")
    Session = sessionmaker(bind=membership_pg_engine, autoflush=False)
    with Session.begin() as db:
        user = m.User(username="position-owner", hashed_password="x", credits=10)
        other = m.User(username="position-other", hashed_password="x", credits=10)
        db.add_all([user, other])
        db.flush()
        uid, other_id = user.id, other.id
    app = FastAPI()
    app.include_router(paid_analysis.router, prefix="/api/v1/analysis")
    active_user = SimpleNamespace(id=uid)
    app.dependency_overrides[require_writable_user] = lambda: active_user
    app.dependency_overrides[get_current_user] = lambda: active_user

    def db_dep():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_dep
    app.state.paid_analysis_client = SimpleNamespace()
    calls = []

    async def analyze(**kwargs):
        calls.append(kwargs)
        return result(kwargs["request_id"], visits=kwargs["max_visits"])

    app.state.paid_analysis_client.analyze = analyze

    def payload(*, key="once", sgf=SGF, profile="normal"):
        parsed = canonical_analysis_input(sgf, "position", profile)
        with Session() as db:
            token = ops.quote_operation(
                db,
                user_id=uid,
                now=datetime.now(timezone.utc),
                kind="position",
                fingerprint=parsed["fingerprint"],
                profile=profile,
                units=1 if profile == "normal" else 4,
                environment="test",
                secret=settings.SECRET_KEY,
            )["token"]
        return {"sgf": sgf, "profile": profile, "quote_token": token, "idempotency_key": key}

    return app, Session, uid, other_id, active_user, calls, payload


@pytest.mark.asyncio
async def test_position_replay_and_owned_territory_hint_reuse(service):
    app, Session, uid, _, _, calls, payload = service
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        body = payload()
        first = await c.post("/api/v1/analysis/positions", json=body)
        assert first.status_code == 200, first.text
        data = first.json()
        assert data["state"] == "succeeded" and len(data["result"]["ownership"]) == 81
        assert data["result"]["moves"][0]["move"] == "C3"
        assert (await c.post("/api/v1/analysis/positions", json=body)).json() == data
        owned = await c.post("/api/v1/analysis/positions", json=payload(key="hint"))
        assert owned.status_code == 200, owned.text
        assert (await c.get("/api/v1/analysis/positions/" + data["operation_id"])).json() == data
    assert len(calls) == 1 and calls[0]["expected_model_sha256"] == MODEL_SHA256
    with Session() as db:
        assert db.get(m.User, uid).credits == 9


@pytest.mark.asyncio
async def test_wrong_model_refunds_without_partial_result(service):
    app, Session, uid, _, _, calls, payload = service

    async def wrong(**kwargs):
        calls.append(kwargs)
        data = result(kwargs["request_id"])
        data["_wrapper"]["model_sha256"] = "0" * 64
        return data

    app.state.paid_analysis_client.analyze = wrong
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/api/v1/analysis/positions", json=payload())
        assert response.status_code == 200, response.text
        assert response.json()["state"] == "refunded" and "result" not in response.json()
    with Session() as db:
        assert db.get(m.User, uid).credits == 10
        assert db.query(m.BillingOperation).one().result is None


@pytest.mark.asyncio
async def test_private_owner_and_same_key_different_history(service):
    app, _, _, other, user, calls, payload = service
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        first = await c.post("/api/v1/analysis/positions", json=payload())
        conflict = await c.post("/api/v1/analysis/positions", json=payload(sgf="(;SZ[9];B[cc];W[dd])"))
        assert conflict.status_code == 409
        user.id = other
        assert (await c.get("/api/v1/analysis/positions/" + first.json()["operation_id"])).status_code == 404
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "late_generation", "oversized"])
async def test_failed_or_late_engine_result_cannot_charge_or_deliver(service, failure):
    import asyncio
    from datetime import timedelta

    app, Session, uid, _, _, calls, payload = service

    async def fail(**kwargs):
        calls.append(kwargs)
        if failure == "timeout":
            raise asyncio.TimeoutError()
        if failure == "late_generation":
            with Session.begin() as db:
                op = db.query(m.BillingOperation).one()
                op.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                db.flush()
                ops.reconcile_expired_positions(db, now=datetime.now(timezone.utc))
        data = result(kwargs["request_id"])
        if failure == "oversized":
            data["moveInfos"][0]["pv"] = ["C3" * 40000]
        return data

    app.state.paid_analysis_client.analyze = fail
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        body = payload()
        response = await c.post("/api/v1/analysis/positions", json=body)
        assert response.status_code == 200, response.text
        assert response.json()["state"] == "refunded" and "result" not in response.json()
        replay = await c.post("/api/v1/analysis/positions", json=body)
        assert replay.json()["state"] == "refunded"
    assert len(calls) == 1
    with Session() as db:
        assert db.get(m.User, uid).credits == 10
        assert db.query(m.BillingOperation).one().result is None


@pytest.mark.asyncio
async def test_expired_receipt_is_retained_and_old_key_never_restarts_gpu(service):
    from datetime import timedelta

    app, Session, _, _, _, calls, payload = service
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        body = payload()
        first = (await c.post("/api/v1/analysis/positions", json=body)).json()
        with Session.begin() as db:
            op = db.query(m.BillingOperation).one()
            op.result_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        receipt = await c.get("/api/v1/analysis/positions/" + first["operation_id"])
        assert receipt.json()["state"] == "result_expired" and "result" not in receipt.json()
        assert (await c.post("/api/v1/analysis/positions", json=body)).status_code == 410
    assert len(calls) == 1
    with Session() as db:
        assert db.query(m.BillingOperation).one().result is None


@pytest.mark.asyncio
async def test_inflight_replay_does_not_start_second_gpu_and_paused_keeps_owned_read(service, monkeypatch):
    import asyncio
    from katrain.web.core.config import settings

    app, _, _, _, _, calls, payload = service
    entered, release = asyncio.Event(), asyncio.Event()

    async def delayed(**kwargs):
        calls.append(kwargs)
        entered.set()
        await release.wait()
        return result(kwargs["request_id"])

    app.state.paid_analysis_client.analyze = delayed
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        body = payload()
        pending = asyncio.create_task(c.post("/api/v1/analysis/positions", json=body))
        await entered.wait()
        replay = await c.post("/api/v1/analysis/positions", json=body)
        assert replay.json()["state"] == "running"
        release.set()
        done = await pending
        monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "paused")
        assert (await c.post("/api/v1/analysis/positions", json=body)).json()["state"] == "succeeded"
        refused = await c.post(
            "/api/v1/analysis/positions", json={**body, "idempotency_key": "new", "sgf": "(;SZ[9];B[cc])"}
        )
        assert refused.status_code == 503
    assert done.status_code == 200 and len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("sgf", ["(;SZ[9])", "(;SZ[9]AB[aa][bb]PL[W])"])
async def test_cloud_accepts_complete_zero_move_and_setup_sgf_without_local_session(service, sgf):
    app, _, _, _, _, calls, payload = service

    async def zero(**kwargs):
        calls.append(kwargs)
        data = result(kwargs["request_id"])
        data["turnNumber"] = 0
        return data

    app.state.paid_analysis_client.analyze = zero
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/api/v1/analysis/positions", json=payload(sgf=sgf))
        assert response.status_code == 200 and response.json()["state"] == "succeeded", response.text
    assert calls[0]["moves"] == []


@pytest.mark.asyncio
async def test_board_switch_discards_private_response_and_never_writes_local_wallet(service, monkeypatch):
    from katrain.web.core.remote_client import RemoteAPIClient
    from katrain.web.core.repository import RepositoryDispatcher
    from katrain.web.core.config import settings

    app, Session, uid, other, _, calls, payload = service
    remote = RemoteAPIClient("http://cloud.test", "paid-box")
    await remote._client.aclose()
    sent = []

    async def handle(request):
        sent.append(request.headers["Authorization"])
        remote.set_tokens("token-b", user_id=other)
        return httpx.Response(200, json={"state": "succeeded", "result": {"ownership": [1]}})

    remote._client = httpx.AsyncClient(base_url="http://cloud.test", transport=httpx.MockTransport(handle))
    remote.set_tokens("token-a", user_id=uid)
    app.state.repository_dispatcher = RepositoryDispatcher(
        SimpleNamespace(is_online=True), None, None, None, None, remote_client=remote
    )
    body = payload()
    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/api/v1/analysis/positions", json=body)
        assert response.status_code == 401 and "result" not in response.json()
    await remote.close()
    assert sent == ["Bearer token-a"] and calls == []
    with Session() as db:
        assert db.get(m.User, uid).credits == 10 and db.get(m.User, other).credits == 10
        assert db.query(m.BillingOperation).count() == 0


@pytest.mark.asyncio
async def test_ranked_guard_rechecked_before_result_settlement_and_delivery(service):
    app, Session, uid, _, _, calls, payload = service
    pending = []
    app.state.ai_ladder_repo = SimpleNamespace(get_pending_game=lambda user: pending[0] if pending else None)

    async def become_ranked(**kwargs):
        calls.append(kwargs)
        pending.append("ranked")
        return result(kwargs["request_id"])

    app.state.paid_analysis_client.analyze = become_ranked
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/api/v1/analysis/positions", json=payload())
        assert response.status_code == 403 and "result" not in response.json()
    with Session() as db:
        assert db.get(m.User, uid).credits == 10
