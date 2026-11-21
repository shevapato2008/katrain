import hashlib
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.core.db import Base as WebBase
from katrain.web.core.models_db import KifuAlbum, KifuAnalysisJob, KifuAnalysisMove
from katrain.web.api.v1.endpoints.kifu import KIFU_MODEL_SHA256, get_kifu_analysis
from katrain.web.core.repository import RemoteServiceUnavailableError
from katrain.cron.kifu_parameters import resolve_parameters


SGF = "(;GM[1]SZ[19]RU[Chinese]KM[7.5]PB[Black]PW[White];B[pd])"


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    WebBase.metadata.create_all(engine, tables=[KifuAlbum.__table__, KifuAnalysisJob.__table__, KifuAnalysisMove.__table__])
    return sessionmaker(bind=engine)()


@pytest.mark.asyncio
async def test_kifu_analysis_separate_store_duplicate_and_obsolete_sgf():
    db = _db()
    try:
        db.add(KifuAlbum(id=1, player_black="Black", player_white="White", source_path="a.sgf", sgf_content=SGF, move_count=1))
        db.add(KifuAlbum(id=2, player_black="Black", player_white="White", source_path="b.sgf", sgf_content=SGF, duplicate_of_id=1, move_count=1))
        db.flush()
        job = KifuAnalysisJob(
            album_id=1,
            sgf_sha256=hashlib.sha256(SGF.encode()).hexdigest(),
            model_sha256=KIFU_MODEL_SHA256,
            requested_visits=2000,
            status="completed",
            total_moves=1,
            analyzed_moves=1,
            analysis_parameters=resolve_parameters(SGF),
        )
        db.add(job)
        db.flush()
        for number in (0, 1):
            db.add(
                KifuAnalysisMove(
                    job_id=job.id,
                    move_number=number,
                    root_visits=2003,
                    parameter_sha256=resolve_parameters(SGF)["parameter_sha256"],
                    winrate=0.5,
                    score_lead=0,
                    top_moves=[],
                    ownership=[],
                )
            )
        db.commit()
        db.add(KifuAnalysisJob(album_id=1, sgf_sha256=hashlib.sha256(SGF.encode()).hexdigest(),
                               model_sha256=KIFU_MODEL_SHA256, requested_visits=2000,
                               status="pending", total_moves=1, analyzed_moves=0))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(repository_dispatcher=None)))
        result = await get_kifu_analysis(request, 2, db)
        assert (result["album_id"], result["canonical_album_id"], result["status"]) == (2, 1, "completed")
        assert [row["move_number"] for row in result["moves"]] == [0, 1]
        db.query(KifuAlbum).filter(KifuAlbum.id == 1).first().sgf_content += ";W[dd]"
        db.commit()
        obsolete = await get_kifu_analysis(request, 1, db)
        assert obsolete["status"] == "unavailable" and obsolete["moves"] == []
        # Existing rows from a previous model can never surface as the current report.
        db.query(KifuAlbum).filter(KifuAlbum.id == 1).first().sgf_content = SGF
        db.query(KifuAnalysisJob).filter(KifuAnalysisJob.id == job.id).first().model_sha256 = "0" * 64
        db.commit()
        wrong_model = await get_kifu_analysis(request, 1, db)
        assert wrong_model["status"] == "unavailable" and wrong_model["moves"] == []
    finally:
        db.close()


@pytest.mark.asyncio
async def test_board_mode_cloud_failure_is_unavailable():
    dispatcher = SimpleNamespace(kifu_get_analysis=AsyncMock(side_effect=RemoteServiceUnavailableError("offline")))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(repository_dispatcher=dispatcher)))
    with pytest.raises(HTTPException) as error:
        await get_kifu_analysis(request, 1, None)
    assert error.value.status_code == 503


@pytest.fixture
def kifu_worker(monkeypatch):
    from katrain.cron.db import Base as CronBase
    from katrain.cron.models import (
        KifuAlbumDB, KifuAnalysisJobDB, KifuAnalysisMoveDB, ReportTaskDB, LiveMatchDB, LiveAnalysisDB,
    )
    from katrain.cron.jobs import kifu_analyze

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    CronBase.metadata.create_all(engine, tables=[
        KifuAlbumDB.__table__, KifuAnalysisJobDB.__table__, KifuAnalysisMoveDB.__table__,
        ReportTaskDB.__table__, LiveMatchDB.__table__, LiveAnalysisDB.__table__,
    ])
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add(KifuAlbumDB(id=1, sgf_content=SGF))
        db.add(
            KifuAnalysisJobDB(
                album_id=1,
                sgf_sha256=hashlib.sha256(SGF.encode()).hexdigest(),
                model_sha256=KIFU_MODEL_SHA256,
                requested_visits=2000,
                status="pending",
                total_moves=1,
                analyzed_moves=0,
                analysis_parameters=resolve_parameters(SGF),
            )
        )
        db.commit()

    monkeypatch.setattr(kifu_analyze, "SessionLocal", sessions)
    monkeypatch.setattr(kifu_analyze.config, "KATAGO_EXPECTED_MODEL_SHA256", KIFU_MODEL_SHA256)
    return kifu_analyze.KifuAnalyzeJob(), sessions


def _depth_response(request_id, turn, visits=2003):
    return {
        "id": request_id,
        "turnNumber": turn,
        "isDuringSearch": False,
        "_wrapper": {"model_sha256": KIFU_MODEL_SHA256, "model_sha256_verified": True, "selected_model": "transformer"},
        "rootInfo": {"visits": visits, "winrate": 0.51, "scoreLead": 0.3},
        "moveInfos": [{"move": "Q16", "visits": visits, "winrate": 0.51, "scoreLead": 0.3, "prior": 0.2}],
        "ownership": [0.0] * 361,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(("visits", "status"), [((1999, 2003, 2003), "completed"), ((1999,) * 3, "failed")])
async def test_kifu_worker_commits_only_depth_verified_positions(kifu_worker, visits, status):
    from katrain.cron.models import KifuAnalysisJobDB, KifuAnalysisMoveDB

    worker, sessions = kifu_worker
    outcomes = iter(visits)

    async def analyze(**kwargs):
        return _depth_response(kwargs["request_id"], kwargs["analyze_turns"][0], next(outcomes))

    worker.client.analyze = AsyncMock(side_effect=analyze)
    for _ in visits:
        await worker.run()
    with sessions() as db:
        job = db.query(KifuAnalysisJobDB).one()
        rows = db.query(KifuAnalysisMoveDB).order_by(KifuAnalysisMoveDB.move_number).all()
        assert job.status == status
        assert [row.move_number for row in rows] == ([0, 1] if status == "completed" else [])
        assert all(row.root_visits >= 2000 for row in rows)


@pytest.mark.asyncio
async def test_kifu_worker_resumes_after_repeated_transient_engine_failures(kifu_worker, monkeypatch):
    from katrain.cron.jobs import kifu_analyze
    from katrain.cron.models import KifuAnalysisJobDB, KifuAnalysisMoveDB

    worker, sessions = kifu_worker
    now = 1000
    monkeypatch.setattr(kifu_analyze, "monotonic", lambda: now)
    request = httpx.Request("POST", "http://engine/analyze")
    failures = [
        httpx.ConnectError("offline", request=request),
        httpx.ReadTimeout("timed out", request=request),
        httpx.HTTPStatusError("rate limited", request=request, response=httpx.Response(429)),
        httpx.HTTPStatusError("unavailable", request=request, response=httpx.Response(503)),
    ]
    outcomes = iter([None, *failures, None])

    async def analyze(**kwargs):
        failure = next(outcomes)
        if failure:
            raise failure
        return _depth_response(kwargs["request_id"], kwargs["analyze_turns"][0])

    worker.client.analyze = AsyncMock(side_effect=analyze)
    await worker.run()
    with sessions() as db:
        initial_position_id = db.query(KifuAnalysisMoveDB).one().id

    for _ in failures:
        now += 61
        await worker.run()
    with sessions() as db:
        job = db.query(KifuAnalysisJobDB).one()
        assert (job.status, job.retry_count) == ("pending", 0)
        assert "HTTPStatusError" in job.error_message
        assert db.query(KifuAnalysisMoveDB).one().id == initial_position_id

    await worker.run()
    assert worker.client.analyze.await_count == 5
    now += 61
    await worker.run()

    with sessions() as db:
        job = db.query(KifuAnalysisJobDB).one()
        assert (job.status, job.analyzed_moves, job.error_message) == ("completed", 1, None)
        rows = db.query(KifuAnalysisMoveDB).order_by(KifuAnalysisMoveDB.move_number).all()
        assert [row.move_number for row in rows] == [0, 1]
        assert rows[0].id == initial_position_id
    calls = worker.client.analyze.await_args_list
    assert [call.kwargs["analyze_turns"] for call in calls] == [[0], [1], [1], [1], [1], [1]]
    assert len({call.kwargs["request_id"] for call in calls}) == len(calls)


@pytest.mark.asyncio
async def test_kifu_worker_discards_error_from_reset_job(kifu_worker):
    from katrain.cron.models import KifuAnalysisJobDB

    worker, sessions = kifu_worker

    async def analyze(**kwargs):
        with sessions() as db:
            # A reset and fresh run may keep the same SGF, parameters and position.
            job = db.query(KifuAnalysisJobDB).one()
            job.started_at += timedelta(seconds=1)
            db.commit()
        request = httpx.Request("POST", "http://engine/analyze")
        raise httpx.HTTPStatusError("bad request", request=request, response=httpx.Response(400))

    worker.client.analyze = AsyncMock(side_effect=analyze)
    await worker.run()
    with sessions() as db:
        job = db.query(KifuAnalysisJobDB).one()
        assert (job.status, job.retry_count, job.error_message) == ("running", 0, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sgf", "move_count"),
    [
        ("(;GM[1]SZ[19]RU[Chinese]KM[7.5])", 0),
        ("(;GM[1]SZ[19]RU[Chinese]KM[7.5]AB[aa:bb];W[cc])", 1),
    ],
)
async def test_kifu_worker_rejects_unrepresentable_game(kifu_worker, sgf, move_count):
    from katrain.cron.models import KifuAlbumDB, KifuAnalysisJobDB

    worker, sessions = kifu_worker
    with sessions() as db:
        db.query(KifuAlbumDB).one().sgf_content = sgf
        job = db.query(KifuAnalysisJobDB).one()
        job.sgf_sha256 = hashlib.sha256(sgf.encode()).hexdigest()
        job.analysis_parameters = resolve_parameters(sgf)
        job.total_moves = move_count
        db.commit()

    async def analyze(request_id, analyze_turns, **kwargs):
        return _depth_response(request_id, analyze_turns[0])

    worker.client.analyze = AsyncMock(side_effect=analyze)
    await worker.run()
    worker.client.analyze.assert_not_awaited()
    with sessions() as db:
        job = db.query(KifuAnalysisJobDB).one()
        assert job.status == "failed"
        assert job.error_message


@pytest.mark.asyncio
async def test_hourly_worker_rejects_mismatched_configuration_before_touching_queue(monkeypatch):
    from katrain.cron.jobs import kifu_analyze

    monkeypatch.setattr(kifu_analyze.config, "KIFU_AUTO_ANALYSIS_ENABLED", True)
    monkeypatch.setattr(kifu_analyze.config, "KATAGO_EXPECTED_MODEL_SHA256", "0" * 64)
    worker = kifu_analyze.KifuAnalyzeJob()
    monkeypatch.setattr(kifu_analyze, "SessionLocal", lambda: pytest.fail("mismatched worker touched the queue"))
    with pytest.raises(RuntimeError, match="professional report model"):
        await worker.run()


@pytest.mark.asyncio
async def test_illegal_position_reported_by_engine_cannot_complete_report(kifu_worker):
    from katrain.cron.models import KifuAnalysisJobDB, KifuAnalysisMoveDB

    worker, sessions = kifu_worker

    async def analyze(request_id, analyze_turns, **kwargs):
        if analyze_turns == [0]:
            return _depth_response(request_id, 0)
        return {"error": "Illegal move in analysis request"}

    worker.client.analyze = AsyncMock(side_effect=analyze)
    for _ in range(4):
        await worker.run()
    with sessions() as db:
        job = db.query(KifuAnalysisJobDB).one()
        assert (job.status, job.retry_count) == ("failed", 3)
        assert "Illegal move" in job.error_message
        assert db.query(KifuAnalysisMoveDB).one().move_number == 0


@pytest.mark.asyncio
async def test_failed_admission_retains_missing_komi_diagnostic():
    sgf = SGF.replace("KM[7.5]", "")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(repository_dispatcher=None)))
    with _db() as db:
        db.add(KifuAlbum(id=1, player_black="Black", player_white="White", source_path="a.sgf", sgf_content=sgf))
        db.flush()
        db.add(KifuAnalysisJob(
            album_id=1,
            sgf_sha256=hashlib.sha256(sgf.encode()).hexdigest(),
            model_sha256=KIFU_MODEL_SHA256,
            requested_visits=2000,
            status="failed",
            total_moves=1,
        ))
        db.commit()
        result = await get_kifu_analysis(request, 1, db)
    assert result["status"] == "rules_unresolved"
    assert result["parameter_error"]["code"] == "missing_komi"
    assert result["moves"] == []
