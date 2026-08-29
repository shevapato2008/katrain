"""Tests for the report analyzer job (now in katrain-cron).

Tests the core analysis logic by patching SessionLocal and KataGoClient.
"""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db


# ── Fake KataGo response ──


def _fake_katago_response(move_number: int) -> dict:
    return {
        "rootInfo": {
            "scoreLead": float(move_number),
            "winrate": 0.5 + move_number * 0.01,
        },
        "moveInfos": [
            {
                "move": "Q16",
                "visits": 500,
                "winrate": 0.52,
                "scoreLead": 1.5,
                "prior": 0.2,
                "pv": ["Q16", "D4"],
                "playSelectionValue": 0.73,
                "order": 1,
            }
        ],
        "ownership": [0.0] * (19 * 19),
    }


# ── Helpers ──


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    models_db.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def _seed_task(SessionLocal, sgf: str = "(;FF[4]SZ[19];B[pd];W[dp])", move_count: int = 2):
    with SessionLocal() as session:
        user = models_db.User(username="analyzer-user", hashed_password="fakehash")
        session.add(user)
        session.commit()
        session.refresh(user)

        game = models_db.UserGame(
            user_id=user.id,
            sgf_content=sgf,
            source="import",
            move_count=move_count,
        )
        session.add(game)
        session.commit()
        session.refresh(game)

        task = models_db.ReportTask(
            user_id=user.id,
            user_game_id=game.id,
            report_type="normal",
            requested_visits=500,
            status="pending",
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return task.id


def _seed_tasks(SessionLocal, count: int):
    with SessionLocal() as session:
        user = models_db.User(username="analyzer-batch", hashed_password="fakehash")
        session.add(user)
        session.commit()
        session.refresh(user)

        game = models_db.UserGame(
            user_id=user.id,
            sgf_content="(;FF[4]SZ[19];B[pd];W[dp])",
            source="import",
            move_count=2,
        )
        session.add(game)
        session.commit()
        session.refresh(game)

        task_ids = []
        for index in range(count):
            task = models_db.ReportTask(
                user_id=user.id,
                user_game_id=game.id,
                report_type="deep" if index % 2 else "normal",
                requested_visits=2000 if index % 2 else 500,
                status="pending",
            )
            session.add(task)
            session.flush()
            task_ids.append(task.id)
        session.commit()
        return task_ids


# ── Tests ──


def test_report_analyzer_defaults_to_three_workers():
    with patch("katrain.cron.jobs.report_analyze.config") as mock_config:
        mock_config.REPORT_CONCURRENCY = 3
        mock_config.REPORT_POLL_INTERVAL = 2.0
        from katrain.cron.jobs.report_analyze import ReportAnalyzerJob

        job = ReportAnalyzerJob()
        assert job.max_concurrent_tasks == 3


@pytest.mark.asyncio
async def test_report_analyzer_retries_then_fails():
    SessionLocal = _make_session()
    task_id = _seed_task(SessionLocal)

    with patch("katrain.cron.jobs.report_analyze.SessionLocal", return_value=SessionLocal()):
        # Need to patch SessionLocal as a callable that returns sessions
        with patch("katrain.cron.jobs.report_analyze.SessionLocal") as mock_sl:
            mock_sl.side_effect = lambda: SessionLocal()
            mock_sl.__enter__ = lambda self: SessionLocal()

            from katrain.cron.jobs.report_analyze import ReportAnalyzerJob, MAX_RETRIES

            job = ReportAnalyzerJob()
            job._running = True
            # Mock KataGo to always fail
            job._katago = MagicMock()
            job._katago.analyze = AsyncMock(side_effect=RuntimeError("boom"))

            for _ in range(MAX_RETRIES):
                await job._process_task(task_id)

    with SessionLocal() as session:
        task = session.query(models_db.ReportTask).filter_by(id=task_id).one()
        assert task.status == "failed"
        assert task.retry_count == MAX_RETRIES
        assert "Analysis failed at move 0" in task.error_message


@pytest.mark.asyncio
async def test_report_analyzer_completes_task():
    SessionLocal = _make_session()
    task_id = _seed_task(SessionLocal)

    async def fake_analyze(**kwargs):
        move_number = kwargs.get("analyze_turns", [0])[0]
        return _fake_katago_response(move_number)

    with patch("katrain.cron.jobs.report_analyze.SessionLocal") as mock_sl:
        mock_sl.side_effect = lambda: SessionLocal()

        from katrain.cron.jobs.report_analyze import ReportAnalyzerJob

        job = ReportAnalyzerJob()
        job._running = True
        job._katago = MagicMock()
        job._katago.analyze = AsyncMock(side_effect=fake_analyze)

        await job._process_task(task_id)

    with SessionLocal() as session:
        task = session.query(models_db.ReportTask).filter_by(id=task_id).one()
        assert task.status == "completed"
        assert task.analyzed_moves == 2
        moves = (
            session.query(models_db.ReportTaskMove)
            .filter_by(task_id=task_id)
            .order_by(models_db.ReportTaskMove.move_number.asc())
            .all()
        )
        assert len(moves) == 3  # move 0, 1, 2
        assert moves[0].top_moves[0]["psv"] == pytest.approx(0.73)


@pytest.mark.asyncio
async def test_report_analyzer_resumes_from_existing_moves():
    SessionLocal = _make_session()
    task_id = _seed_task(SessionLocal)

    # Pre-seed move 0 as already analyzed
    with SessionLocal() as session:
        session.add(
            models_db.ReportTaskMove(
                task_id=task_id,
                move_number=0,
                status="success",
                winrate=0.5,
                score_lead=0.0,
                visits=500,
                top_moves=[{"move": "Q16", "visits": 500}],
            )
        )
        task = session.query(models_db.ReportTask).filter_by(id=task_id).one()
        task.analyzed_moves = 0
        session.commit()

    call_log = []

    async def fake_analyze(**kwargs):
        move_number = kwargs.get("analyze_turns", [0])[0]
        call_log.append(move_number)
        return _fake_katago_response(move_number)

    with patch("katrain.cron.jobs.report_analyze.SessionLocal") as mock_sl:
        mock_sl.side_effect = lambda: SessionLocal()

        from katrain.cron.jobs.report_analyze import ReportAnalyzerJob

        job = ReportAnalyzerJob()
        job._running = True
        job._katago = MagicMock()
        job._katago.analyze = AsyncMock(side_effect=fake_analyze)

        await job._process_task(task_id)

    with SessionLocal() as session:
        task = session.query(models_db.ReportTask).filter_by(id=task_id).one()
        assert task.status == "completed"
        assert task.analyzed_moves == 2
        # Should have skipped move 0 and analyzed moves 1 and 2
        assert call_log == [1, 2]


@pytest.mark.asyncio
async def test_让子局带着让子石去分析_变化图不进主线():
    """解析对了不等于送出去的也对 —— 调用处原来写死 `initial_stones=[]`。

    这条盯的是 `_analyze_position` 真正交给 KataGo 的那份请求：
    让子石必须在 `initial_stones` 里、先手必须是白、变化图那两手不许出现在 `moves` 里。
    解析本身在 `tests/web_ui/test_cron_sgf.py`；两处缺一不可 ——
    历史上正是「解析读到了、调用处扔了」这种形状。
    """
    SessionLocal = _make_session()
    # 二子局。分歧点上有两个子树：第一个是主线的延续，第二个是变化图。
    task_id = _seed_task(
        SessionLocal,
        sgf="(;FF[4]SZ[19]HA[2]KM[0.5]AB[dd][pp];W[qq];B[cc](;W[dq];B[fc])(;W[ee];B[ff]))",
        move_count=4,
    )

    calls = []

    async def fake_analyze(**kwargs):
        calls.append(kwargs)
        return _fake_katago_response(kwargs.get("analyze_turns", [0])[0])

    with patch("katrain.cron.jobs.report_analyze.SessionLocal") as mock_sl:
        mock_sl.side_effect = lambda: SessionLocal()

        from katrain.cron.jobs.report_analyze import ReportAnalyzerJob

        job = ReportAnalyzerJob()
        job._running = True
        job._katago = MagicMock()
        job._katago.analyze = AsyncMock(side_effect=fake_analyze)

        await job._process_task(task_id)

    # 主线四手 ⇒ 第 0…4 手五帧。变化图那两手要是被拼进来就会多两帧。
    assert len(calls) == 5
    for kwargs in calls:
        assert kwargs["initial_stones"] == [["B", "D16"], ["B", "Q4"]]
        assert kwargs["initial_player"] == "W"
        assert kwargs["komi"] == 0.5
    assert calls[-1]["moves"] == [["W", "R3"], ["B", "C17"], ["W", "D3"], ["B", "F17"]]
    # E15 / F14 是变化图那两手 —— 一次都不该出现。
    played = [move for kwargs in calls for move in kwargs["moves"]]
    assert not [move for move in played if move[1] in ("E15", "F14")]

    with SessionLocal() as session:
        task = session.query(models_db.ReportTask).filter_by(id=task_id).one()
        # 摆子不是着手：总手数是 4（不含两颗让子石，也不含变化图那两手）。
        assert task.total_moves == 4
        assert task.status == "completed"
