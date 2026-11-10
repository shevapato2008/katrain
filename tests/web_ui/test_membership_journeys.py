"""Cross-module HTTP journeys in an independently marked, private PostgreSQL schema.

Only KataGo's HTTP transport is simulated. Auth, HMAC payment facts, quotes,
reservation/settlement, repositories, worker claims and API responses are real.
"""

import json
import os
from types import SimpleNamespace

import httpx
import pytest
from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy.orm import sessionmaker

from tests.web_ui.membership_test_support import membership_pg_engine
from katrain.web.core import models_db as m
from katrain.web.core.billing_catalog import MODEL_SHA256

SGF = "(;FF[4]SZ[9]KM[7.5]RU[chinese];B[aa];W[bb])"
OTHER_SGF = "(;FF[4]SZ[9]KM[7.5]RU[chinese];B[cc];W[dd])"


@pytest.fixture
def journey(membership_pg_engine, monkeypatch):
    # Import global factories while the runner's explicit in-memory URL is in
    # force. Neither global engine is used or started by this test application.
    from katrain.web.core.config import settings
    from katrain.web.core.db import get_db
    from katrain.cron import db as cron_db
    from katrain.cron.jobs import report_analyze as worker
    from katrain.cron.clients import katago
    from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token
    from katrain.web.core.billing_environment import validate_runtime_environment
    from katrain.web.core.user_game_repo import UserGameRepository, UserGameAnalysisRepository

    monkeypatch.setenv("KATRAIN_DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    for key, value in {
        "KATRAIN_MODE": "server",
        "KATRAIN_ENVIRONMENT": "test",
        "MEMBERSHIP_MODE": "enabled",
        "PAYMENTS_MODE": "mock",
        "BILLING_ENFORCED": True,
        "PAYMENT_MOCK_EVENT_SECRET": "journey-isolated-test-hmac",
    }.items():
        monkeypatch.setattr(settings, key, value)
    # This queries current_database() and the separately provisioned, read-only
    # TEST marker before creating subjects or installing any test dependency.
    assert validate_runtime_environment(membership_pg_engine, settings) is True
    Session = sessionmaker(bind=membership_pg_engine, autoflush=False)
    assert Session.kw.get("expire_on_commit", True) is True
    with Session.begin() as db:
        users = [
            m.User(username="journey-owner", hashed_password="x", credits=137),
            m.User(username="journey-admin", hashed_password="x", is_admin=True),
            m.User(username="journey-qualified", hashed_password="x", credits=0),
            m.User(username="journey-unverified", hashed_password="x", credits=0),
        ]
        db.add_all(users)
        db.flush()
        ids = {u.username.removeprefix("journey-"): u.id for u in users}
    headers = {name: {"Authorization": "Bearer " + create_access_token({"sub": "journey-" + name})} for name in ids}

    from katrain.web.api.v1.api import api_router
    from katrain.web.api.v1.endpoints.payment_test import register_test_payment_routes

    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    # api_router may already have been imported by a legacy-mode test in the
    # same pytest process. Register the actual configuration-gated routes once.
    if not any(getattr(r, "path", None) == "/api/v1/payments/test/events" for r in app.routes):
        test_router = APIRouter()
        register_test_payment_routes(test_router, runtime_settings=settings)
        app.include_router(test_router, prefix="/api/v1")

    def db_dependency():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_dependency
    app.state.user_repo = SQLAlchemyUserRepository(Session)
    app.state.user_game_repo = UserGameRepository(Session)
    app.state.user_game_analysis_repo = UserGameAnalysisRepository(Session)
    app.state.report_session_factory = Session
    monkeypatch.setattr(worker, "SessionLocal", Session)
    monkeypatch.setattr(cron_db, "SessionLocal", Session)

    engine = SimpleNamespace(calls=[], fail=False)

    def engine_http(request):
        assert request.url.host == "journey-engine.invalid"
        payload = json.loads(request.content)
        engine.calls.append(payload)
        if engine.fail:
            return httpx.Response(503, json={"error": "controlled engine outage"})
        visits, size = payload["maxVisits"], payload["boardXSize"]
        return httpx.Response(
            200,
            json={
                "id": payload["id"],
                "turnNumber": payload["analyzeTurns"][-1],
                "isDuringSearch": False,
                "_wrapper": {
                    "model_sha256": MODEL_SHA256,
                    "model_sha256_verified": True,
                    "selected_model": "paid",
                },
                "rootInfo": {"visits": visits, "winrate": 0.5, "scoreLead": 1.0},
                "moveInfos": [
                    {"move": "C3", "visits": visits, "winrate": 0.5, "scoreLead": 1.0, "prior": 0.1, "pv": ["C3"]}
                ],
                "ownership": [0.0] * (size * size),
            },
        )

    # Swap the transport at the module boundary, retaining the real client,
    # request serialization and strict final-result validator.
    monkeypatch.setattr(
        katago,
        "httpx",
        SimpleNamespace(AsyncClient=lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(engine_http), **kw)),
    )
    client = katago.KataGoClient(base_url="http://journey-engine.invalid", analyze_path="/analyze")
    app.state.paid_analysis_client = client
    job = worker.ReportAnalyzerJob()
    job._katago = client
    return SimpleNamespace(
        app=app, Session=Session, ids=ids, headers=headers, engine=engine, job=job, settings=settings
    )


def api_client(j, subject="owner", surface="galaxy"):
    # Independent browser clients share the authenticated API/account contract.
    # This is not an assertion about actual RK/kiosk hardware or board proxying.
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=j.app),
        base_url="http://journey.test",
        headers={**j.headers[subject], "User-Agent": "membership-journey-" + surface},
    )


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


async def buy_pro(j, client):
    from katrain.web.core.payment_mock import sign_event

    order = ok(
        await client.post("/api/v1/billing/orders", json={"sku": "membership_pro", "idempotency_key": "buy-pro"})
    )
    assert order["status"] == "pending" and order["amount_fen"] == 9900
    assert order["kind"] == "membership" and order["fulfillment"] is None
    event = {
        "order_id": order["id"],
        "owner_id": j.ids["owner"],
        "environment": "test",
        "amount_fen": order["amount_fen"],
        "provider_tx_id": "journey-pro-provider-fact",
        "status": "paid",
        "deliver": True,
    }
    async with api_client(j, "admin") as admin:
        paid = ok(
            await admin.post(
                "/api/v1/payments/test/events",
                json=event,
                headers={"X-Mock-Signature": sign_event(event, secret=j.settings.PAYMENT_MOCK_EVENT_SECRET)},
            )
        )
    assert paid["status"] == "paid"
    receipt = ok(await client.get("/api/v1/billing/orders/" + order["id"]))
    assert receipt["status"] == "paid" and receipt["fulfillment"]["plan_code"] == "pro"
    return receipt


async def quote(client, kind="position", *, sgf=SGF, game_id=None):
    body = {"kind": kind, "profile": "normal", **({"game_id": game_id} if game_id else {"sgf": sgf})}
    response = await client.post("/api/v1/billing/quotes", json=body)
    data = ok(response)
    # These are the frontend Membership/BillingQuote HTTP contract fields.
    assert data["kind"] == kind and data["profile"] == "normal"
    assert data["source_policy"] == "membership_then_wallet"
    assert data["wallet_max_credits"] == (0 if data["source"] == "owned" else data["units"])
    assert isinstance(data["token"], str) and data["environment"] == "test"
    return data


async def position(client, q, key, *, sgf=SGF):
    return ok(
        await client.post(
            "/api/v1/analysis/positions",
            json={
                "profile": "normal",
                "sgf": sgf,
                "quote_token": q["token"],
                "idempotency_key": key,
            },
        )
    )


async def save_game(client, sgf=SGF):
    return ok(
        await client.post(
            "/api/v1/user-games/",
            json={
                "source": "import",
                "sgf_content": sgf,
                "board_size": 9,
                # The server must derive report N from SGF, rather than trust this field.
                "move_count": 0,
            },
        )
    )["id"]


async def report(client, q, gid, key):
    return ok(
        await client.post(
            "/api/v1/reports/",
            json={
                "user_game_id": gid,
                "report_type": "normal",
                "quote_token": q["token"],
                "idempotency_key": key,
            },
        )
    )


async def run_report(j, created):
    claim = j.job._claim_pending_task(with_fence=True)
    assert claim[0] == created["id"] and claim[2] == created["operation_id"]
    with j.Session() as db:
        task = db.get(m.ReportTask, claim[0])
        op = db.get(m.BillingOperation, claim[2])
        assert task.generation == op.generation == claim[1] > 0
        assert op.status == "running" and task.operation_id == op.id and op.task_id == task.id
        assert task.model_sha256 == op.model_sha256 == MODEL_SHA256
        assert task.total_moves == 2 and task.requested_visits == 500
    await j.job._process_task(claim[0], generation=claim[1], operation_id=claim[2])
    with j.Session() as db:
        assert db.get(m.ReportTask, claim[0]).status == "completed"
        # Cron generates private task assets; HTTP settlement alone publishes them.
        assert db.get(m.BillingOperation, claim[2]).status == "running"
        assert db.query(m.UserGameAnalysis).filter_by(game_id=created["user_game_id"]).count() == 0


def comparable_usage(data):
    return {k: v for k, v in data.items() if k != "server_now"}


@pytest.mark.asyncio
async def test_pro_checkout_position_reuse_and_complete_report_share_one_account(journey):
    j = journey
    async with api_client(j) as galaxy, api_client(j, surface="kiosk") as kiosk:
        await buy_pro(j, galaxy)
        initial = ok(await galaxy.get("/api/v1/billing/usage"))
        assert initial["plan"]["current"]["code"] == "pro"
        assert initial["term"]["limit"] == 27090 and initial["week"]["limit"] == 9030
        assert initial["wallet"] == {"credits": 137, "display_points": "1.37"}
        assert comparable_usage(initial) == comparable_usage(ok(await kiosk.get("/api/v1/billing/usage")))
        q = await quote(galaxy)
        assert q["source"] == "membership" and q["units"] == 1
        first = await position(galaxy, q, "position-confirm")
        assert first["state"] == "succeeded" and first["source"] == "membership"
        assert first["units"] == 1 and first["wallet_credits"] == 0
        assert len(first["result"]["ownership"]) == 81 and first["result"]["moves"][0]["move"] == "C3"
        assert first["result"]["rootInfo"]["visits"] == 500
        assert await position(kiosk, q, "position-confirm") == first
        owned_quote = await quote(kiosk)
        assert owned_quote["source"] == "owned"
        owned = await position(kiosk, owned_quote, "toggle-hint-territory")
        assert owned["source"] == "owned" and owned["result"] == first["result"]
        assert ok(await kiosk.get(f"/api/v1/analysis/positions/{first['operation_id']}")) == first
        assert len(j.engine.calls) == 1

        gid = await save_game(galaxy)
        rq = await quote(galaxy, "report", game_id=gid)
        assert rq["units"] == 3 and rq["source"] == "membership"
        created = await report(galaxy, rq, gid, "report-confirm")
        assert created["total_moves"] == 2 and created["source"] == "membership"
        assert (await kiosk.get(f"/api/v1/reports/{created['id']}/moves")).status_code == 409
        await run_report(j, created)
        moves = ok(await kiosk.get(f"/api/v1/reports/{created['id']}/moves"))
        assert [row["move_number"] for row in moves] == [0, 1, 2]
        assert all(row["root_visits"] >= 500 and row["ownership"] for row in moves)
        final = ok(await galaxy.get("/api/v1/billing/usage"))
        assert final["term"]["used"] == final["week"]["used"] == 4
        assert final["term"]["reserved"] == final["week"]["reserved"] == 0
        assert final["wallet"] == initial["wallet"]
        assert comparable_usage(final) == comparable_usage(ok(await kiosk.get("/api/v1/billing/usage")))
    assert [p["analyzeTurns"][0] for p in j.engine.calls[1:]] == [0, 1, 2]
    assert len(j.engine.calls) == 4
    assert all(p["maxVisits"] == 500 and p["includeOwnership"] is True for p in j.engine.calls)
    with j.Session() as db:
        assert db.get(m.BillingOperation, created["operation_id"]).status == "committed"
        assert db.query(m.UserGameAnalysis).filter_by(game_id=gid).count() == 3
        assert db.get(m.User, j.ids["owner"]).credits == 137


@pytest.mark.asyncio
@pytest.mark.parametrize("exhausted", ["term", "week"])
async def test_engine_refund_and_signed_fallback_preserve_integer_wallet(journey, exhausted):
    j = journey
    async with api_client(j) as client:
        await buy_pro(j, client)
        before = ok(await client.get("/api/v1/billing/usage"))
        membership_quote = await quote(client)
        j.engine.fail = True
        failed = await position(client, membership_quote, "membership-outage")
        assert failed["source"] == "membership" and failed["state"] == "refunded" and "result" not in failed
        after = ok(await client.get("/api/v1/billing/usage"))
        assert after["term"] == before["term"] and after["week"] == before["week"]
        assert after["wallet"] == before["wallet"]

        # Accept a real server-signed membership quote, then exhaust one budget
        # before confirm. The signed whole-operation wallet cap authorizes fallback.
        fallback_quote = await quote(client, sgf=OTHER_SGF)
        with j.Session.begin() as db:
            if exhausted == "term":
                term = db.query(m.MembershipTerm).filter_by(user_id=j.ids["owner"]).one()
                term.used = term.limit
            else:
                bucket = db.query(m.QuotaBucket).filter_by(user_id=j.ids["owner"], kind="membership_week").one()
                bucket.used = bucket.allowance
            db.flush()
        exhausted_usage = ok(await client.get("/api/v1/billing/usage"))
        wallet_failed = await position(client, fallback_quote, "wallet-outage", sgf=OTHER_SGF)
        assert wallet_failed["source"] == "wallet" and wallet_failed["state"] == "refunded"
        assert ok(await client.get("/api/v1/billing/usage"))["wallet"]["credits"] == 137
        j.engine.fail = False
        paid = await position(client, fallback_quote, "wallet-confirm", sgf=OTHER_SGF)
        assert paid["source"] == "wallet" and paid["wallet_credits"] == paid["units"] == 1
        assert paid["state"] == "succeeded"
        final = ok(await client.get("/api/v1/billing/usage"))
        assert final["wallet"] == {"credits": 136, "display_points": "1.36"}
        assert final["term"] == exhausted_usage["term"] and final["week"] == exhausted_usage["week"]
    with j.Session() as db:
        operations = db.query(m.BillingOperation).order_by(m.BillingOperation.id).all()
        assert [(o.source, o.status) for o in operations] == [
            ("membership", "refunded"),
            ("wallet", "refunded"),
            ("wallet", "committed"),
        ]
        assert operations[0].term_id is not None and operations[0].week_bucket_id is not None
        assert all(o.term_id is None and o.week_bucket_id is None for o in operations[1:])


@pytest.mark.asyncio
async def test_test_qualified_free_report_is_not_position_credit_or_repeat_grant(journey):
    from katrain.web.api.v1.endpoints.auth import get_current_user
    from katrain.web.api.v1.endpoints.billing import get_trusted_free_eligibility

    j = journey
    async with api_client(j, "unverified") as ordinary:
        usage = ok(await ordinary.get("/api/v1/billing/usage"))
        assert usage["free"]["eligible"] is False and usage["free"]["reason"] == "verification_required"
        denied = await ordinary.post("/api/v1/billing/quotes", json={"kind": "report", "profile": "normal", "sgf": SGF})
        assert denied.status_code == 403 and denied.json()["detail"]["code"] == "verification_required"

    # The fixture already verified the actual DB + independent TEST marker.
    # This controlled subject is evidence for eligibility consumption, not P3
    # verification: the production dependency remains fail-closed by default.
    async def qualified_test_subject(user=Depends(get_current_user)):
        return user.id == j.ids["qualified"]

    j.app.dependency_overrides[get_trusted_free_eligibility] = qualified_test_subject
    async with api_client(j, "qualified") as client:
        usage = ok(await client.get("/api/v1/billing/usage"))
        assert usage["free"]["eligible"] and usage["free"]["remaining"] == 1
        assert usage["wallet"]["credits"] == 0 and usage["term"] is None
        position_denied = await client.post(
            "/api/v1/billing/quotes", json={"kind": "position", "profile": "normal", "sgf": SGF}
        )
        assert position_denied.status_code == 402
        gid = await save_game(client)
        q = await quote(client, "report", game_id=gid)
        assert q["source"] == "free_report" and q["units"] == 3
        created = await report(client, q, gid, "free-report-confirm")
        assert created["source"] == "free_report" and created["wallet_credits"] == 0
        await run_report(j, created)
        assert len(ok(await client.get(f"/api/v1/reports/{created['id']}/moves"))) == 3
        assert ok(await client.delete("/api/v1/user-games/" + gid))["status"] == "deleted"
        usage = ok(await client.get("/api/v1/billing/usage"))
        assert usage["free"]["remaining"] == 0 and usage["free"]["reason"] == "weekly_report_used"
        denied = await client.post(
            "/api/v1/billing/quotes", json={"kind": "report", "profile": "normal", "sgf": OTHER_SGF}
        )
        assert denied.status_code == 402
    assert len(j.engine.calls) == 3
    with j.Session() as db:
        receipt = db.get(m.BillingOperation, created["operation_id"])
        assert receipt.source == "free_report" and receipt.status == "committed"
        assert db.query(m.BillingOperation).filter_by(user_id=j.ids["qualified"]).count() == 1
        assert db.get(m.User, j.ids["qualified"]).credits == 0
        assert db.query(m.MembershipTerm).filter_by(user_id=j.ids["qualified"]).count() == 0
