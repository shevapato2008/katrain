import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.report.analyzer import MAX_RETRIES, ReportAnalyzerService


class FakeRouter:
    def __init__(self, fail_moves: set[int] | None = None):
        self.fail_moves = fail_moves or set()
        self.calls: list[int] = []

    async def route(self, payload):
        move_number = payload["analyzeTurns"][0]
        self.calls.append(move_number)
        if move_number in self.fail_moves:
            raise RuntimeError(f"boom at {move_number}")
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


class BlockingRouter(FakeRouter):
    def __init__(self):
        super().__init__()
        self.release = asyncio.Event()
        self.two_started = asyncio.Event()
        self.active_calls = 0
        self.max_active_calls = 0

    async def route(self, payload):
        self.active_calls += 1
        self.max_active_calls = max(self.max_active_calls, self.active_calls)
        if self.active_calls >= 2:
            self.two_started.set()
        try:
            if payload["analyzeTurns"][0] == 0:
                await self.release.wait()
            return await super().route(payload)
        finally:
            self.active_calls -= 1


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    models_db.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def _seed_task(SessionLocal):
    with SessionLocal() as session:
        user = models_db.User(username="analyzer-user", hashed_password="fakehash")
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


def test_report_analyzer_defaults_to_three_workers():
    SessionLocal = _make_session()
    service = ReportAnalyzerService(SessionLocal, FakeRouter())
    assert service.max_concurrent_tasks == 3


@pytest.mark.asyncio
async def test_report_analyzer_retries_then_fails():
    SessionLocal = _make_session()
    task_id = _seed_task(SessionLocal)
    service = ReportAnalyzerService(SessionLocal, FakeRouter(fail_moves={0}))
    service._running = True

    for _ in range(MAX_RETRIES):
        await service._process_task(task_id)

    with SessionLocal() as session:
        task = session.query(models_db.ReportTask).filter_by(id=task_id).one()
        assert task.status == "failed"
        assert task.retry_count == MAX_RETRIES
        assert task.error_message == "Analysis failed at move 0"


@pytest.mark.asyncio
async def test_report_analyzer_resumes_from_existing_moves():
    SessionLocal = _make_session()
    task_id = _seed_task(SessionLocal)
    router = FakeRouter()
    service = ReportAnalyzerService(SessionLocal, router)
    service._running = True

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

    await service._process_task(task_id)

    with SessionLocal() as session:
        task = session.query(models_db.ReportTask).filter_by(id=task_id).one()
        move_numbers = [
            row.move_number
            for row in session.query(models_db.ReportTaskMove)
            .filter_by(task_id=task_id)
            .order_by(models_db.ReportTaskMove.move_number.asc())
            .all()
        ]
        assert task.status == "completed"
        assert task.analyzed_moves == 2
        assert move_numbers == [0, 1, 2]
        assert router.calls == [1, 2]


@pytest.mark.asyncio
async def test_report_analyzer_persists_play_selection_value():
    SessionLocal = _make_session()
    task_id = _seed_task(SessionLocal)
    service = ReportAnalyzerService(SessionLocal, FakeRouter())
    service._running = True

    await service._process_task(task_id)

    with SessionLocal() as session:
        move = (
            session.query(models_db.ReportTaskMove)
            .filter_by(task_id=task_id, move_number=0)
            .one()
        )
        assert move.top_moves[0]["psv"] == pytest.approx(0.73)


@pytest.mark.asyncio
async def test_report_analyzer_processes_multiple_tasks_concurrently():
    SessionLocal = _make_session()
    task_ids = _seed_tasks(SessionLocal, count=2)
    router = BlockingRouter()
    service = ReportAnalyzerService(SessionLocal, router, poll_interval=0.01, max_concurrent_tasks=2)

    service.start()
    await asyncio.wait_for(router.two_started.wait(), timeout=0.2)
    router.release.set()

    for _ in range(50):
      with SessionLocal() as session:
          statuses = [
              session.query(models_db.ReportTask).filter_by(id=task_id).one().status
              for task_id in task_ids
          ]
      if all(status == "completed" for status in statuses):
          break
      await asyncio.sleep(0.02)

    await service.stop()

    with SessionLocal() as session:
        statuses = [
            session.query(models_db.ReportTask).filter_by(id=task_id).one().status
            for task_id in task_ids
        ]

    assert router.max_active_calls >= 2
    assert statuses == ["completed", "completed"]
