"""Paid report assets: one complete, fenced attempt or a full refund."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import sessionmaker

from tests.web_ui.membership_test_support import membership_pg_engine
from katrain.web.core import models_db as m, billing_operations as ops
from katrain.web.core.billing_catalog import CATALOG_VERSION, MODEL_SHA256, report_units
from katrain.web.core.billing_quotes import canonical_analysis_input

SGF = "(;FF[4]SZ[9]KM[7.5]RU[chinese];B[aa];W[bb])"


@pytest.fixture
def reports(membership_pg_engine, monkeypatch):
    from katrain.web.api.v1.endpoints import reports as endpoint, user_games
    from katrain.web.api.v1.endpoints.auth import get_current_user, require_writable_user
    from katrain.web.core.config import settings
    from katrain.web.core.user_game_repo import UserGameRepository, UserGameAnalysisRepository

    monkeypatch.setattr(settings, "MEMBERSHIP_MODE", "enabled")
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    monkeypatch.setattr(settings, "KATRAIN_ENVIRONMENT", "test")
    # Match both web and cron runtime session semantics.
    Session = sessionmaker(bind=membership_pg_engine, autoflush=False)
    with Session.begin() as db:
        user = m.User(username="paid-report", hashed_password="x", credits=100)
        db.add(user)
        db.flush()
        game = m.UserGame(user_id=user.id, source="import", sgf_content=SGF, move_count=0)
        db.add(game)
        db.flush()
        uid, gid = user.id, game.id
    app = FastAPI()
    app.include_router(endpoint.router, prefix="/reports")
    app.include_router(user_games.router, prefix="/games")
    app.state.report_session_factory = Session
    app.state.user_game_repo = UserGameRepository(Session)
    app.state.user_game_analysis_repo = UserGameAnalysisRepository(Session)
    current = SimpleNamespace(id=uid, is_guest=False)
    app.dependency_overrides[get_current_user] = lambda: current
    app.dependency_overrides[require_writable_user] = lambda: current
    return SimpleNamespace(app=app, Session=Session, uid=uid, gid=gid, settings=settings, monkeypatch=monkeypatch)


def acceptance(r, key="create", profile="normal"):
    canonical = canonical_analysis_input(SGF, "report", profile)
    with r.Session() as db:
        token = ops.quote_operation(
            db,
            user_id=r.uid,
            now=datetime.now(timezone.utc),
            kind="report",
            fingerprint=canonical["fingerprint"],
            profile=profile,
            units=report_units(canonical["move_count"], profile),
            environment="test",
            secret=r.settings.SECRET_KEY,
        )["token"]
    return {
        "user_game_id": r.gid,
        "report_type": "deep" if profile == "advanced" else "normal",
        "quote_token": token,
        "idempotency_key": key,
    }


async def create(r, **kw):
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        response = await client.post("/reports/", json=acceptance(r, **kw))
    assert response.status_code == 200, response.text
    return response.json()


def claim_task(job, task_id):
    claim = job._claim_pending_task(with_fence=True)
    assert claim[0] == task_id
    return {"generation": claim[1], "operation_id": claim[2]}


def completed(r, tid, *, missing=None, visits=500):
    with r.Session.begin() as db:
        task = db.get(m.ReportTask, tid)
        task.status, task.analyzed_moves = "completed", 2
        for n in range(3):
            if n == missing:
                continue
            db.add(
                m.ReportTaskMove(
                    task_id=tid,
                    move_number=n,
                    status="success",
                    root_visits=visits,
                    winrate=0.5,
                    score_lead=0,
                    top_moves=[{"move": "C3", "visits": visits}],
                    ownership=[[0.0] * 9] * 9,
                )
            )


@pytest.mark.asyncio
async def test_atomic_paid_create_replay_and_missing_quote_fail_closed(reports):
    r = reports
    payload = acceptance(r)
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        missing = await client.post("/reports/", json={"user_game_id": r.gid})
        assert missing.status_code == 422
        first = await client.post("/reports/", json=payload)
        assert first.status_code == 200, first.text
        replay = await client.post("/reports/", json=payload)
        assert replay.status_code == 200 and replay.json()["id"] == first.json()["id"]
    with r.Session() as db:
        task = db.query(m.ReportTask).one()
        op = db.query(m.BillingOperation).one()
        assert (task.total_moves, task.requested_visits, task.billing_version) == (2, 500, CATALOG_VERSION)
        assert task.analysis_sgf and task.sgf_hash
        assert task.operation_id == op.id and op.task_id == task.id
        assert db.get(m.User, r.uid).credits == 97
        assert first.json()["wallet_display_points"] == "0.03"


@pytest.mark.asyncio
async def test_failed_prefix_full_refund_then_full_retry_and_owned_read(reports):
    r = reports
    first = await create(r)
    with r.Session.begin() as db:
        task = db.get(m.ReportTask, first["id"])
        task.status, task.analyzed_moves = "failed", 1
        db.add(m.ReportTaskMove(task_id=task.id, move_number=0, status="success", root_visits=500))
        db.add(m.UserGameAnalysis(game_id=r.gid, move_number=0, status="success", winrate=0.9))
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        denied = await client.get(f"/reports/{first['id']}/moves")
        assert denied.status_code == 409
        assert r.app.state.user_game_analysis_repo.get_analysis(r.gid) == []
        with r.Session() as db:
            assert db.get(m.User, r.uid).credits == 100
            assert db.get(m.BillingOperation, first["operation_id"]).status == "refunded"
        retry = await client.post(f"/reports/{first['id']}/retry", json=acceptance(r, "retry"))
        assert retry.status_code == 200, retry.text
        assert retry.json()["operation_id"] != first["operation_id"]
    with r.Session() as db:
        assert db.query(m.ReportTaskMove).count() == 0
        assert db.get(m.User, r.uid).credits == 97
    completed(r, first["id"])
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        moves = await client.get(f"/reports/{first['id']}/moves")
        assert moves.status_code == 200 and len(moves.json()) == 3
        repeat = await client.post("/reports/", json={"user_game_id": r.gid})
        assert repeat.status_code == 200 and repeat.json()["id"] == first["id"]
    with r.Session() as db:
        assert db.get(m.User, r.uid).credits == 97
        assert db.get(m.BillingOperation, retry.json()["operation_id"]).status == "committed"
        assert db.query(m.UserGameAnalysis).count() == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("missing,visits", [(0, 500), (1, 500), (2, 500), (None, 499)])
async def test_analyzed_moves_does_not_prove_complete_depth(reports, missing, visits):
    r = reports
    task = await create(r)
    completed(r, task["id"], missing=missing, visits=visits)
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        response = await client.get(f"/reports/{task['id']}/moves")
        assert response.status_code == 409
    with r.Session() as db:
        assert db.get(m.User, r.uid).credits == 100
        assert db.query(m.UserGameAnalysis).count() == 0


@pytest.mark.asyncio
async def test_pending_delete_is_blocked_terminal_delete_keeps_receipt(reports):
    r = reports
    task = await create(r)
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        assert (await client.delete(f"/games/{r.gid}")).status_code == 409
        completed(r, task["id"])
        assert (await client.get(f"/reports/{task['id']}/moves")).status_code == 200
        assert (await client.delete(f"/games/{r.gid}")).status_code == 200
    with r.Session() as db:
        assert db.get(m.BillingOperation, task["operation_id"]).status == "committed"
        assert db.get(m.User, r.uid).credits == 97


@pytest.mark.asyncio
async def test_worker_claim_generation_and_late_worker_cannot_publish(reports):
    from katrain.cron.jobs import report_analyze as worker

    r = reports
    task = await create(r)
    r.monkeypatch.setattr(worker, "SessionLocal", r.Session)
    job = worker.ReportAnalyzerJob()
    fence = claim_task(job, task["id"])
    with r.Session() as db:
        before = db.get(m.ReportTask, task["id"]).generation
        assert before > 0 and db.get(m.BillingOperation, task["operation_id"]).generation == before

    async def reset_during_analysis(**kwargs):
        with r.Session.begin() as db:
            row = db.get(m.ReportTask, task["id"])
            row.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)
        job._reset_runtime_stale_tasks()
        return {"status": "success", "root_visits": 500, "winrate": 0.5, "score_lead": 0}

    r.monkeypatch.setattr(job, "_analyze_position", reset_during_analysis)
    await job._process_task(task["id"], **fence)
    with r.Session() as db:
        row = db.get(m.ReportTask, task["id"])
        assert row.generation > before and row.status == "failed"
        assert db.query(m.ReportTaskMove).count() == 0


@pytest.mark.asyncio
async def test_worker_uses_frozen_model_and_all_positions_without_global_model(reports):
    from katrain.cron.jobs import report_analyze as worker
    from katrain.cron.clients.katago import KataGoClient

    r = reports
    task = await create(r, profile="advanced")
    r.monkeypatch.setattr(worker, "SessionLocal", r.Session)
    r.monkeypatch.setattr(worker.config, "KATAGO_EXPECTED_MODEL_SHA256", None)
    calls = []

    async def analyze(**kw):
        calls.append(kw)
        response = {
            "id": kw["request_id"],
            "turnNumber": kw["analyze_turns"][0],
            "isDuringSearch": False,
            "_wrapper": {"model_sha256": MODEL_SHA256, "model_sha256_verified": True, "selected_model": "paid"},
            "rootInfo": {"visits": 2000, "winrate": 0.5, "scoreLead": 0},
            "moveInfos": [{"move": "C3", "visits": 1000, "winrate": 0.5, "scoreLead": 0, "prior": 0.2}],
            "ownership": [0.0] * 81,
        }
        KataGoClient.validate_result(
            response, kw["request_id"], kw["analyze_turns"][0], 9, kw["expected_model_sha256"], kw["max_visits"]
        )
        return response

    job = worker.ReportAnalyzerJob()
    job._katago.analyze = analyze
    fence = claim_task(job, task["id"])
    await job._process_task(task["id"], **fence)
    assert [c["analyze_turns"][0] for c in calls] == [0, 1, 2]
    assert all(c["expected_model_sha256"] == MODEL_SHA256 and c["max_visits"] == 2000 for c in calls)
    with r.Session() as db:
        assert db.get(m.ReportTask, task["id"]).status == "completed"
        assert db.query(m.UserGameAnalysis).count() == 0


@pytest.mark.asyncio
async def test_paid_requeue_and_generic_save_cannot_reactivate_or_overwrite(reports):
    from katrain.cron.jobs import requeue_reports
    from katrain.web.core.user_game_repo import ProtectedReportAnalysisError

    r = reports
    task = await create(r)
    completed(r, task["id"])
    r.monkeypatch.setattr(requeue_reports, "SessionLocal", r.Session)
    r.monkeypatch.setattr(requeue_reports.config, "HUMAN_SL_PROFILE", "test")
    stats = requeue_reports.requeue(commit=True)
    assert stats["requeued"] == 0
    with r.Session() as db:
        assert db.query(m.ReportTaskMove).count() == 3
        assert db.get(m.ReportTask, task["id"]).status == "completed"
    with pytest.raises(ProtectedReportAnalysisError):
        r.app.state.user_game_analysis_repo.upsert(r.gid, 0, status="success", winrate=0.99)


@pytest.mark.asyncio
async def test_owned_new_key_receipt_replays_without_new_task_or_charge(reports):
    r = reports
    first = await create(r)
    completed(r, first["id"])
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        assert (await client.get(f"/reports/{first['id']}/moves")).status_code == 200
        body = acceptance(r, "owned-view")
        first_view = await client.post("/reports/", json=body)
        replay = await client.post("/reports/", json=body)
        assert first_view.status_code == replay.status_code == 200
        assert first_view.json()["id"] == first["id"]
        assert first_view.json()["source"] == "owned"
        assert first_view.json()["operation_id"] == replay.json()["operation_id"] != first["operation_id"]
        assert first_view.json()["wallet_credits"] == 0
    with r.Session() as db:
        assert db.query(m.ReportTask).count() == 1 and db.get(m.User, r.uid).credits == 97


@pytest.mark.asyncio
async def test_idempotency_conflict_never_reuses_different_report(reports):
    r = reports
    first = await create(r)
    with r.Session.begin() as db:
        db.get(m.UserGame, r.gid).sgf_content = SGF.replace("B[aa]", "B[cc]")
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        response = await client.post(
            "/reports/", json={"user_game_id": r.gid, "quote_token": "irrelevant", "idempotency_key": "create"}
        )
        assert response.status_code == 409 and response.json()["detail"]["code"] == "idempotency_conflict"
    with r.Session() as db:
        assert db.query(m.BillingOperation).count() == 1 and db.get(m.User, r.uid).credits == 97


@pytest.mark.asyncio
async def test_persisted_receipt_still_settles_when_mode_paused(reports):
    r = reports
    first = await create(r)
    completed(r, first["id"])
    r.monkeypatch.setattr(r.settings, "MEMBERSHIP_MODE", "paused")
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        assert (await client.get(f"/reports/{first['id']}/moves")).status_code == 200
        denied = await client.post(
            f"/reports/{first['id']}/retry", json={"quote_token": "unused", "idempotency_key": "retry"}
        )
        assert denied.status_code == 503
    with r.Session() as db:
        assert db.get(m.BillingOperation, first["operation_id"]).status == "committed"


@pytest.mark.asyncio
@pytest.mark.parametrize("migrated", [True, False])
async def test_activated_user_cannot_create_legacy_unbilled_report(reports, migrated):
    r = reports
    if migrated:
        await create(r)
    else:
        r.app.state.membership_guard_active = True
    r.monkeypatch.setattr(r.settings, "MEMBERSHIP_MODE", "legacy")
    r.monkeypatch.setattr(r.settings, "BILLING_ENFORCED", False)
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        response = await client.post("/reports/", json={"user_game_id": r.gid, "report_type": "deep", "force": True})
        assert response.status_code >= 400
    with r.Session() as db:
        assert db.query(m.ReportTask).count() == int(migrated)


@pytest.mark.asyncio
@pytest.mark.parametrize("free", [False, True])
async def test_switch_to_enabled_preserves_only_original_legacy_grace_authorization(reports, free):
    from katrain.web.core import billing, quota

    r = reports
    with r.Session.begin() as db:
        task = m.ReportTask(
            user_id=r.uid,
            user_game_id=r.gid,
            report_type="normal",
            requested_visits=500,
            status="failed",
            total_moves=2,
            analyzed_moves=1,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(task)
        db.flush()
        tid = task.id
        if free:
            task.free_grant_period = quota.period_key("week")
            db.add(
                m.QuotaBucket(
                    user_id=r.uid,
                    kind="free_report",
                    period_key=task.free_grant_period,
                    allowance=1,
                    used=1,
                    reserved=0,
                )
            )
    with r.Session() as db:
        if not free:
            task = db.get(m.ReportTask, tid)
            ref = f"report:{tid}"
            billing.reserve(db, r.uid, 2, "report", ref)
            task.charge_ref = ref
            db.commit()
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        response = await client.post(f"/reports/{tid}/retry")
        assert response.status_code == 200, response.text
    with r.Session() as db:
        task = db.get(m.ReportTask, tid)
        assert task.status == "pending" and task.operation_id is None and task.billing_version is None
        assert db.query(m.BillingOperation).count() == 0
        assert db.get(m.User, r.uid).credits == (100 if free else 98)


@pytest.mark.asyncio
async def test_authorization_and_task_rollback_together(reports):
    from katrain.web.api.v1.endpoints import reports as endpoint

    r = reports

    def fail_binding(*args, **kw):
        raise RuntimeError("simulated task insert failure")

    r.monkeypatch.setattr(endpoint, "_bind_paid_attempt", fail_binding)
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        with pytest.raises(RuntimeError, match="simulated task insert failure"):
            await client.post("/reports/", json=acceptance(r))
    with r.Session() as db:
        assert db.query(m.BillingOperation).count() == db.query(m.ReportTask).count() == 0
        assert db.get(m.User, r.uid).credits == 100


@pytest.mark.asyncio
async def test_automatic_worker_retry_restarts_the_entire_generation(reports):
    from katrain.cron.jobs import report_analyze as worker

    r = reports
    task = await create(r)
    r.monkeypatch.setattr(worker, "SessionLocal", r.Session)
    job = worker.ReportAnalyzerJob()
    seen = []

    async def analyze(**kw):
        seen.append(kw["move_number"])
        if len(seen) == 2:
            return None
        return {"status": "success", "root_visits": 500, "winrate": 0.5, "score_lead": 0}

    r.monkeypatch.setattr(job, "_analyze_position", analyze)
    fence = claim_task(job, task["id"])
    await job._process_task(task["id"], **fence)
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        assert (await client.get(f"/reports/{task['id']}/moves")).status_code == 409
    fence = claim_task(job, task["id"])
    with r.Session() as db:
        assert db.query(m.ReportTaskMove).count() == 0
    await job._process_task(task["id"], **fence)
    assert seen == [0, 1, 0, 1, 2]
    with r.Session() as db:
        row = db.get(m.ReportTask, task["id"])
        assert row.status == "completed"
        assert row.generation == db.get(m.BillingOperation, task["operation_id"]).generation


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["membership", "free_report"])
async def test_original_allowance_settles_once_and_deletion_keeps_used(reports, source):
    from katrain.web.api.v1.endpoints.billing import get_trusted_free_eligibility
    from katrain.web.core import membership

    r = reports
    now = datetime.now(timezone.utc)
    with r.Session.begin() as db:
        db.get(m.User, r.uid).credits = 0
        if source == "membership":
            order = m.RechargeOrder(
                user_id=r.uid,
                out_trade_no="report-member",
                package_id="plus",
                amount_fen=3900,
                credits=0,
                provider="manual",
                status="paid",
            )
            db.add(order)
            db.flush()
            db.add(
                m.MembershipTerm(
                    user_id=r.uid,
                    plan_id="plus",
                    starts_at=now - timedelta(days=1),
                    ends_at=now + timedelta(days=29),
                    limit=9030,
                    used=0,
                    reserved=0,
                    order_id=order.id,
                    catalog_version=CATALOG_VERSION,
                )
            )
    # This fixture has already checked the actual private PG TEST identity.
    r.app.dependency_overrides[get_trusted_free_eligibility] = lambda: source == "free_report"
    canonical = canonical_analysis_input(SGF, "report", "normal")
    with r.Session() as db:
        q = ops.quote_operation(
            db,
            user_id=r.uid,
            now=now,
            kind="report",
            fingerprint=canonical["fingerprint"],
            profile="normal",
            units=3,
            environment="test",
            secret=r.settings.SECRET_KEY,
            trusted_free_eligible=True,
        )
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        response = await client.post(
            "/reports/", json={"user_game_id": r.gid, "quote_token": q["token"], "idempotency_key": "allowance"}
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["source"] == source and result["wallet_credits"] == 0
        completed(r, result["id"])
        assert (await client.get(f"/reports/{result['id']}/moves")).status_code == 200
        assert (await client.get(f"/reports/{result['id']}/moves")).status_code == 200
        assert (await client.delete(f"/games/{r.gid}")).status_code == 200
    with r.Session() as db:
        bucket = db.query(m.QuotaBucket).filter_by(kind=membership.WEEK_KIND).one()
        assert (bucket.used, bucket.reserved) == (3, 0)
        if source == "membership":
            term = db.query(m.MembershipTerm).one()
            assert (term.used, term.reserved) == (3, 0)
        assert db.get(m.BillingOperation, result["operation_id"]).status == "committed"


@pytest.mark.asyncio
async def test_invalid_receipt_binding_is_a_closed_409(reports):
    r = reports
    task = await create(r)
    with r.Session.begin() as db:
        db.get(m.BillingOperation, task["operation_id"]).task_id = None
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        response = await client.get(f"/reports/{task['id']}/moves")
        assert response.status_code == 409
    assert r.app.state.user_game_analysis_repo.get_analysis(r.gid) == []


@pytest.mark.asyncio
async def test_sgf_changed_during_admission_rolls_back_the_reservation(reports):
    r = reports
    original = ops.reserve_operation_in_transaction

    def reserve_then_change_game(db, **kw):
        result = original(db, **kw)
        # Library edits do not spend money and may commit while admission holds
        # the user row. The endpoint must re-read the authoritative SGF afterward.
        with r.Session.begin() as other:
            other.get(m.UserGame, r.gid).sgf_content = SGF.replace("B[aa]", "B[cc]")
        return result

    r.monkeypatch.setattr(ops, "reserve_operation_in_transaction", reserve_then_change_game)
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        response = await client.post("/reports/", json=acceptance(r))
        assert response.status_code == 409
    with r.Session() as db:
        assert db.query(m.BillingOperation).count() == db.query(m.ReportTask).count() == 0
        assert db.get(m.User, r.uid).credits == 100


@pytest.mark.asyncio
async def test_settler_limit_does_not_get_stuck_on_old_committed_receipts(reports):
    from katrain.web.core.report_settlement import settle_finished_reports

    r = reports
    first = await create(r)
    completed(r, first["id"])
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        assert (await client.get(f"/reports/{first['id']}/moves")).status_code == 200
    second = await create(r, key="advanced", profile="advanced")
    completed(r, second["id"], visits=2000)
    with r.Session() as db:
        assert settle_finished_reports(db, limit=1, user_id=r.uid) == 1
        assert db.get(m.BillingOperation, second["operation_id"]).status == "committed"


@pytest.mark.asyncio
async def test_worker_delayed_before_start_cannot_adopt_a_later_claim(reports):
    from katrain.cron.jobs import report_analyze as worker

    r = reports
    task = await create(r)
    r.monkeypatch.setattr(worker, "SessionLocal", r.Session)
    job = worker.ReportAnalyzerJob()
    claim = job._claim_pending_task(with_fence=True)
    with r.Session.begin() as db:
        row = db.get(m.ReportTask, task["id"])
        row.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)
    job._reset_runtime_stale_tasks()
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        response = await client.post(f"/reports/{task['id']}/retry", json=acceptance(r, "retry"))
        assert response.status_code == 200, response.text
    assert job._claim_pending_task() == task["id"]
    analyze = AsyncMock()
    r.monkeypatch.setattr(job, "_analyze_position", analyze)
    await job._process_task(claim[0], generation=claim[1], operation_id=claim[2])
    analyze.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["enabled", "legacy"])
async def test_session_save_cannot_extract_internal_paid_analysis(reports, mode):
    r = reports
    r.monkeypatch.setattr(r.settings, "MEMBERSHIP_MODE", mode)
    r.app.state.membership_guard_active = True
    extract = MagicMock(side_effect=AssertionError("private analysis must not be extracted"))
    runtime = SimpleNamespace(game_type="free", _do_extract_analysis=extract)
    r.app.state.session_manager = SimpleNamespace(
        get_session=lambda _: SimpleNamespace(katrain=runtime, game_type="free")
    )
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        response = await client.post(f"/games/{r.gid}/analysis/save", json={"game_id": r.gid, "session_id": "live"})
    assert response.status_code == 409
    extract.assert_not_called()


@pytest.mark.asyncio
async def test_diagnosis_reconciles_complete_receipt_and_ignores_failed_newer_report(reports):
    from katrain.web.core.report_diagnosis_repo import ReportDiagnosisRepository

    r = reports
    first = await create(r)
    completed(r, first["id"])
    with r.Session.begin() as db:
        db.get(m.UserGame, r.gid).user_color = "B"
        row = db.query(m.ReportTaskMove).filter_by(task_id=first["id"], move_number=1).one()
        row.actual_player, row.grade = "B", "mistake"
    repo = ReportDiagnosisRepository(r.Session)
    since = datetime.now(timezone.utc) - timedelta(days=1)
    result = repo.recent_graded_moves(r.uid, since=since)
    assert result["moves"] == [{"move_number": 1, "grade": "mistake"}]
    with r.Session() as db:
        assert db.get(m.BillingOperation, first["operation_id"]).status == "committed"
    # The newer completed marker is untrustworthy: it contains only a prefix.
    newer = await create(r, key="deep", profile="advanced")
    with r.Session.begin() as db:
        task = db.get(m.ReportTask, newer["id"])
        task.status, task.analyzed_moves = "completed", 2
        db.add(
            m.ReportTaskMove(
                task_id=task.id, move_number=0, status="success", root_visits=2000, actual_player="B", grade="brilliant"
            )
        )
    result = repo.recent_graded_moves(r.uid, since=since)
    assert result["reports"] == 1 and result["moves"] == [{"move_number": 1, "grade": "mistake"}]
    with r.Session() as db:
        assert db.get(m.ReportTask, newer["id"]).status == "failed"
        assert db.get(m.BillingOperation, newer["operation_id"]).status == "refunded"
    assert repo.recent_graded_moves(r.uid, since=since)["moves"] == result["moves"]


@pytest.mark.asyncio
async def test_retry_failed_report_returns_separately_owned_report_and_receipt(reports):
    r = reports
    failed = await create(r, key="failed-a")
    with r.Session.begin() as db:
        db.get(m.ReportTask, failed["id"]).status = "failed"
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        assert (await client.get(f"/reports/{failed['id']}/moves")).status_code == 409
    owned = await create(r, key="completed-b")
    completed(r, owned["id"])
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        assert (await client.get(f"/reports/{owned['id']}/moves")).status_code == 200
        body = acceptance(r, key="owned-retry-a")
        response = await client.post(f"/reports/{failed['id']}/retry", json=body)
        assert response.status_code == 200, response.text
        replay = await client.post(f"/reports/{failed['id']}/retry", json=body)
        assert replay.status_code == 200, replay.text
    assert response.json() == replay.json()
    assert response.json()["id"] == owned["id"]
    assert response.json()["source"] == "owned" and response.json()["wallet_credits"] == 0
    assert response.json()["operation_id"] not in (failed["operation_id"], owned["operation_id"])
    assert response.json()["authorization_operation_id"] == owned["operation_id"]
    with r.Session() as db:
        task = db.get(m.ReportTask, failed["id"])
        assert task.status == "failed" and task.operation_id == failed["operation_id"]
        assert db.query(m.ReportTask).count() == 2 and db.get(m.User, r.uid).credits == 97
        assert db.query(m.BillingOperation).count() == 3


@pytest.mark.asyncio
async def test_real_ranked_pending_blocks_old_report_quotes_retry_and_private_moves(reports):
    from katrain.web.api.v1.api import api_router
    from katrain.web.core.ai_ladder_ranked import AiLadderRankedRepository
    from katrain.web.core.db import get_db

    r = reports
    r.monkeypatch.setattr(r.settings, "KATRAIN_MODE", "server")
    r.app.include_router(api_router, prefix="/api/v1")

    def db_dependency():
        with r.Session() as db:
            yield db

    r.app.dependency_overrides[get_db] = db_dependency
    r.app.state.ai_ladder_repo = AiLadderRankedRepository(r.Session)
    async with AsyncClient(transport=ASGITransport(app=r.app), base_url="http://test") as client:
        quote = await client.post("/api/v1/billing/quotes", json={"kind": "report", "profile": "advanced", "sgf": SGF})
        assert quote.status_code == 200, quote.text
        owned = await create(r, key="before-ranked")
        completed(r, owned["id"])
        assert (await client.get(f"/api/v1/reports/{owned['id']}/moves")).status_code == 200
        failed = await create(r, key="failed-before-ranked", profile="advanced")
        with r.Session.begin() as db:
            db.get(m.ReportTask, failed["id"]).status = "failed"
        assert (await client.get(f"/api/v1/reports/{failed['id']}/moves")).status_code == 409
        with r.Session.begin() as db:
            db.add(
                m.AiLadderPendingGame(
                    game_id="ranked-live",
                    user_id=r.uid,
                    session_id="ranked-session",
                    user_color="B",
                    game_type="ai_ladder_ranked",
                    opponent_rung=1,
                    opponent_rank_name="18k",
                    opponent_config_snapshot={},
                    opponent_certification_status="certified",
                    opponent_availability="available",
                    opponent_route="server",
                    ai_subtype="test",
                    execution_identity="test",
                )
            )
        assert r.app.state.ai_ladder_repo.get_pending_game(r.uid)
        imported = await client.post("/api/v1/user-games/", json={"sgf_content": SGF, "source": "import"})
        assert imported.status_code == 200, imported.text
        body = {
            "user_game_id": imported.json()["id"],
            "report_type": "deep",
            "quote_token": quote.json()["token"],
            "idempotency_key": "stale-quote-during-ranked",
        }
        assert (await client.post("/api/v1/reports/", json=body)).status_code == 403
        assert (await client.post(f"/api/v1/reports/{failed['id']}/retry", json=body)).status_code == 403
        assert (await client.get(f"/api/v1/reports/{owned['id']}/moves")).status_code == 403
        assert (await client.get(f"/api/v1/reports/{owned['id']}")).status_code == 200
    with r.Session() as db:
        assert db.query(m.BillingOperation).count() == 2 and db.get(m.User, r.uid).credits == 97
