"""Recorder behavior against synthetic SQLite tables created by the web schema."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.cron.models import CronJobRunDB, CronJobStatusDB, LiveMatchDB, UpcomingMatchDB
from katrain.cron.run_recorder import RunRecorder, install_error_capture
from katrain.web.core import models_db


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models_db.Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


class Job:
    def __init__(self, name, behavior):
        self.name = name
        self.behavior = behavior

    async def run(self):
        await self.behavior()


async def ok():
    pass


async def swallowed():
    try:
        raise ValueError("upstream 500")
    except ValueError:
        logging.getLogger("katrain_cron.cleanup").exception("CleanupJob failed")


async def raises():
    raise RuntimeError("boom")


def recorder(session_factory, *jobs):
    install_error_capture()
    instance = RunRecorder(session_factory, clock=Clock())
    assert instance.register([(name, "interval", interval, True) for name, interval in jobs])
    return instance


def status(session_factory, name):
    with session_factory() as session:
        return session.get(CronJobStatusDB, name)


def runs(session_factory, name):
    with session_factory() as session:
        return session.query(CronJobRunDB).filter_by(job_name=name).order_by(CronJobRunDB.id).all()


def test_success_and_short_interval_history(session_factory):
    instance = recorder(session_factory, ("fetch_list", 60), ("poll_moves", 3))
    asyncio.run(instance.run(Job("fetch_list", ok)))
    asyncio.run(instance.run(Job("poll_moves", ok)))
    assert (
        status(session_factory, "fetch_list").last_status,
        [run.status for run in runs(session_factory, "fetch_list")],
    ) == (
        "success",
        ["success"],
    )
    assert status(session_factory, "poll_moves").last_status == "success"
    assert runs(session_factory, "poll_moves") == []


def test_swallowed_error_and_child_task_are_recorded(session_factory):
    instance = recorder(session_factory, ("cleanup", 86400))

    async def work():
        await swallowed()
        await asyncio.create_task(swallowed())

    asyncio.run(instance.run(Job("cleanup", work)))
    row = status(session_factory, "cleanup")
    history = runs(session_factory, "cleanup")
    assert row.last_status == "errors" and row.consecutive_failures == 1
    assert "CleanupJob failed" in row.last_error and "ValueError: upstream 500" in row.last_error
    assert history[0].status == "errors" and history[0].error_count == 2
    assert history[0].error == row.last_error


def test_first_error_is_truncated_but_total_error_count_is_preserved(session_factory):
    instance = recorder(session_factory, ("fetch_list", 1800))

    async def work():
        logger = logging.getLogger("cron.long_error")
        logger.error("first %s", "x" * 3000)
        logger.error("second error")

    asyncio.run(instance.run(Job("fetch_list", work)))
    row = status(session_factory, "fetch_list")
    history = runs(session_factory, "fetch_list")
    assert row.last_status == "errors"
    assert row.last_error.startswith("[cron.long_error] first ")
    assert len(row.last_error) == 2000
    assert "second error" not in row.last_error
    assert history[0].error == row.last_error
    assert history[0].error_count == 2


def test_escaping_exception_is_reraised_and_short_interval_failure_is_kept(session_factory):
    instance = recorder(session_factory, ("poll_moves", 3))
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(instance.run(Job("poll_moves", raises)))
    row = status(session_factory, "poll_moves")
    history = runs(session_factory, "poll_moves")
    assert (row.last_status, row.last_error, row.consecutive_failures) == ("failed", "RuntimeError: boom", 1)
    assert len(history) == 1 and history[0].status == "failed"


def test_errors_outside_run_are_not_attributed(session_factory):
    instance = recorder(session_factory, ("fetch_list", 60))
    logging.getLogger("katrain_cron.elsewhere").error("unrelated")
    asyncio.run(instance.run(Job("fetch_list", ok)))
    assert status(session_factory, "fetch_list").last_status == "success"


def test_recorder_write_failure_does_not_break_job(session_factory, caplog):
    instance = recorder(session_factory, ("fetch_list", 60))
    completed = []

    async def work():
        completed.append(True)

    def db_down():
        raise RuntimeError("db down")

    instance._session_factory = db_down
    with caplog.at_level(logging.WARNING, logger="katrain_cron.recorder"):
        asyncio.run(instance.run(Job("fetch_list", work)))
    assert completed == [True]
    assert "cron run recorder write failed" in caplog.text


def test_registration_closes_previous_process_run_and_removes_renamed_job(session_factory):
    clock = Clock()
    with session_factory() as session:
        session.add(CronJobStatusDB(job_name="old_name", kind="interval", enabled=True, consecutive_failures=0))
        session.add(
            CronJobRunDB(
                job_name="fetch_list", started_at=clock.now - timedelta(minutes=5), status="running", error_count=0
            )
        )
        session.commit()
    instance = RunRecorder(session_factory, clock=clock)
    assert instance.register([("fetch_list", "interval", 60, True)])
    assert status(session_factory, "old_name") is None
    history = runs(session_factory, "fetch_list")
    assert history[0].status == "failed" and history[0].finished_at is not None
    assert "结束前退出" in history[0].error
    row = status(session_factory, "fetch_list")
    assert row.last_status == "failed" and row.last_error == history[0].error


def test_late_table_creation_is_retried_by_heartbeat():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    factory = sessionmaker(bind=engine)
    instance = RunRecorder(factory, clock=Clock())
    assert not instance.register([("fetch_list", "interval", 60, True), ("analyze", "loop", None, False)])
    models_db.Base.metadata.create_all(engine)
    instance.heartbeat({})
    assert status(factory, "fetch_list") is not None
    assert status(factory, "analyze").enabled is False
    engine.dispose()


def test_late_registration_does_not_close_this_process_run(session_factory):
    clock = Clock()
    with session_factory() as session:
        session.add(CronJobRunDB(job_name="fetch_list", started_at=clock.now - timedelta(minutes=5), status="running"))
        session.commit()
    instance = RunRecorder(session_factory, clock=clock)

    def db_down():
        raise RuntimeError("db down")

    instance._session_factory = db_down
    assert not instance.register([("fetch_list", "interval", 60, True)])
    instance._session_factory = session_factory
    clock.now += timedelta(seconds=30)
    with session_factory() as session:
        session.add(CronJobRunDB(job_name="fetch_list", started_at=clock.now, status="running"))
        session.commit()
    instance.heartbeat({})
    assert [run.status for run in runs(session_factory, "fetch_list")] == ["failed", "running"]


def test_loop_crash_and_heartbeat_progress(session_factory):
    clock = Clock()
    instance = RunRecorder(session_factory, clock=clock)
    assert instance.register([("analyze", "loop", None, True)])

    class Loop:
        last_iteration_at = clock.now - timedelta(seconds=2)

        def heartbeat_stats(self):
            return {"in_flight": 3, "capacity": 16}

    instance.record_loop_crash("analyze", RuntimeError("katago gone"))
    instance.heartbeat({"analyze": Loop()})
    row = status(session_factory, "analyze")
    assert row.loop_stats["in_flight"] == 3 and row.last_status == "failed"
    assert row.consecutive_failures == 1 and "katago gone" in row.last_error
    assert [run.status for run in runs(session_factory, "analyze")] == ["failed"]
    Loop.last_iteration_at = clock.now + timedelta(seconds=15)
    instance.heartbeat({"analyze": Loop()})
    assert status(session_factory, "analyze").consecutive_failures == 0


def test_scheduler_routes_first_run_through_recorder():
    from katrain.cron.scheduler import CronScheduler

    scheduler = CronScheduler()
    added = []
    scheduler._scheduler.add_job = lambda func, trigger, **kwargs: added.append((func, trigger, kwargs))
    scheduler._schedule(Job("fetch_list", ok), 60)
    ((func, trigger, kwargs),) = added
    assert func == scheduler._recorder.run and trigger == "interval"
    assert kwargs["args"][0].name == "fetch_list"
    assert kwargs["seconds"] == 60 and kwargs["max_instances"] == 1
    assert kwargs["next_run_time"] is not None


def test_loop_jobs_expose_heartbeat_stats():
    from katrain.cron import config
    from katrain.cron.jobs.analyze import AnalyzeJob
    from katrain.cron.jobs.report_analyze import ReportAnalyzerJob

    analyze, report = AnalyzeJob(), ReportAnalyzerJob()
    assert analyze.last_iteration_at is None and report.last_iteration_at is None
    assert analyze.heartbeat_stats() == {"in_flight": 0, "capacity": config.ANALYSIS_WINDOW_SIZE}
    assert report.heartbeat_stats() == {"in_flight": 0, "capacity": max(1, config.REPORT_CONCURRENCY)}


def test_cleanup_prunes_old_cron_runs(session_factory, monkeypatch):
    from katrain.cron import config
    from katrain.cron.jobs import cleanup

    monkeypatch.setattr(cleanup, "SessionLocal", session_factory)
    now = datetime.now(timezone.utc)
    with session_factory() as session:
        session.add_all(
            [
                CronJobRunDB(
                    job_name="fetch_list",
                    started_at=now - timedelta(days=config.RUNS_RETENTION_DAYS + 1),
                    status="success",
                ),
                CronJobRunDB(job_name="fetch_list", started_at=now - timedelta(days=1), status="success"),
            ]
        )
        session.commit()
    asyncio.run(cleanup.CleanupJob().run())
    assert len(runs(session_factory, "fetch_list")) == 1


def test_cleanup_keeps_match_and_event_deletions_when_cron_table_is_missing(session_factory, monkeypatch):
    from katrain.cron.jobs import cleanup

    monkeypatch.setattr(cleanup, "SessionLocal", session_factory)
    engine = session_factory.kw["bind"]
    with session_factory() as session:
        session.add(
            LiveMatchDB(
                match_id="expired-match",
                source="test",
                source_id="expired-match",
                tournament="Test",
                player_black="Black",
                player_white="White",
                status="finished",
                updated_at=datetime.now(timezone.utc) - timedelta(days=60),
            )
        )
        session.add(
            UpcomingMatchDB(
                event_id="expired-event",
                tournament="Test",
                source="test",
                scheduled_time=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )
        session.commit()
    models_db.CronJobRun.__table__.drop(engine)
    assert "cron_job_runs" not in inspect(engine).get_table_names()

    asyncio.run(cleanup.CleanupJob().run())

    with session_factory() as session:
        assert session.query(LiveMatchDB).filter_by(match_id="expired-match").count() == 0
        assert session.query(UpcomingMatchDB).filter_by(event_id="expired-event").count() == 0


def test_shutdown_during_registration_retry_does_not_start_scheduler():
    from katrain.cron.scheduler import CronScheduler

    async def scenario():
        scheduler = CronScheduler()
        entered = asyncio.Event()
        started = []
        scheduler._recorder.register = lambda jobs: entered.set() or False
        scheduler._recorder.ensure_registered = lambda: False
        scheduler._scheduler.start = lambda: started.append(True)
        start_task = asyncio.create_task(scheduler.start())
        try:
            await asyncio.wait_for(entered.wait(), timeout=1)
            await scheduler.shutdown()
            await asyncio.wait_for(start_task, timeout=1)
            assert scheduler._shutdown_event.is_set()
            assert started == []
        finally:
            if not start_task.done():
                start_task.cancel()
                await asyncio.gather(start_task, return_exceptions=True)

    asyncio.run(scenario())
