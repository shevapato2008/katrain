import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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


SGF = "(;GM[1]SZ[19]KM[7.5]PB[Black]PW[White];B[pd])"


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
        job = KifuAnalysisJob(album_id=1, sgf_sha256=hashlib.sha256(SGF.encode()).hexdigest(),
                              model_sha256=KIFU_MODEL_SHA256, requested_visits=2000,
                              status="completed", total_moves=1, analyzed_moves=1)
        db.add(job)
        db.flush()
        for number in (0, 1):
            db.add(KifuAnalysisMove(job_id=job.id, move_number=number, root_visits=2003,
                                    winrate=0.5, score_lead=0, top_moves=[], ownership=[]))
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


@pytest.mark.asyncio
async def test_kifu_worker_commits_only_depth_verified_positions():
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
        db.add(KifuAnalysisJobDB(album_id=1, sgf_sha256=hashlib.sha256(SGF.encode()).hexdigest(),
                                 model_sha256=KIFU_MODEL_SHA256, requested_visits=2000,
                                 status="pending", total_moves=1, analyzed_moves=0))
        db.commit()

    def response(request_id, turn, visits):
        return {
            "id": request_id, "turnNumber": turn, "isDuringSearch": False,
            "_wrapper": {"model_sha256": KIFU_MODEL_SHA256, "model_sha256_verified": True, "selected_model": "transformer"},
            "rootInfo": {"visits": visits, "winrate": 0.51, "scoreLead": 0.3},
            "moveInfos": [{"move": "Q16", "visits": visits, "winrate": 0.51, "scoreLead": 0.3, "prior": 0.2}],
            "ownership": [0.0] * 361,
        }

    outcomes = [1999, 2003, 2003]
    async def analyze(**kwargs):
        return response(kwargs["request_id"], kwargs["analyze_turns"][0], outcomes.pop(0))

    with patch.object(kifu_analyze, "SessionLocal", sessions), \
         patch.object(kifu_analyze.config, "KATAGO_EXPECTED_MODEL_SHA256", KIFU_MODEL_SHA256):
        worker = kifu_analyze.KifuAnalyzeJob()
        worker.client.analyze = AsyncMock(side_effect=analyze)
        for _ in range(3):
            await worker.run()
        with sessions() as db:
            job = db.query(KifuAnalysisJobDB).one()
            rows = db.query(KifuAnalysisMoveDB).order_by(KifuAnalysisMoveDB.move_number).all()
            assert job.status == "completed"
            assert [row.move_number for row in rows] == [0, 1]
            assert all(row.root_visits >= 2000 for row in rows)
