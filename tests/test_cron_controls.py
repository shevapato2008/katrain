"""Cron honours admin controls: a paused interval job is skipped (and says so); run-now is picked up."""

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.cron.controls import ControlPoller
from katrain.cron.models import CronJobCommandDB, CronJobControlDB, CronJobRunDB, CronJobStatusDB
from katrain.cron.run_recorder import RunRecorder
from katrain.web.core import models_db


@pytest.fixture
def factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models_db.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class Job:
    def __init__(self, name):
        self.name, self.calls = name, 0

    async def run(self):
        self.calls += 1


class FakeScheduler:
    def __init__(self, names):
        self.jobs = {name: FakeApsJob() for name in names}

    def get_job(self, name):
        return self.jobs.get(name)


class FakeApsJob:
    def __init__(self):
        self.next_run_time = None

    def modify(self, next_run_time):
        self.next_run_time = next_run_time


def setup(factory):
    recorder = RunRecorder(factory)
    assert recorder.register([("fetch_list", "interval", 60, True), ("analyze", "loop", None, True)])
    return recorder


def test_a_paused_job_is_skipped_and_recorded_as_paused(factory):
    recorder, job = setup(factory), Job("fetch_list")
    with factory() as db:
        db.add(CronJobControlDB(job_name="fetch_list", paused=True, reason="上游维护中", changed_at=datetime.now(timezone.utc), changed_by="admin:fan"))
        db.commit()
    poller = ControlPoller(factory, recorder, FakeScheduler(["fetch_list"]))
    poller.poll()
    asyncio.run(recorder.run(job))
    assert job.calls == 0
    with factory() as db:
        assert db.get(CronJobStatusDB, "fetch_list").last_status != "paused"  # still describes the last real run
        assert [r.status for r in db.query(CronJobRunDB).filter_by(job_name="fetch_list")] == ["paused"]
    with factory() as db:
        db.get(CronJobControlDB, "fetch_list").paused = False
        db.commit()
    poller.poll()
    asyncio.run(recorder.run(job))
    assert job.calls == 1


def test_run_now_is_handed_to_the_scheduler_and_marked_done(factory):
    recorder = setup(factory)
    scheduler = FakeScheduler(["fetch_list"])
    poller = ControlPoller(factory, recorder, scheduler)  # the cron process starts before the request
    with factory() as db:
        db.add(CronJobCommandDB(job_name="fetch_list", command="run_now", requested_at=datetime.now(timezone.utc), requested_by="admin:fan", state="pending"))
        db.add(CronJobCommandDB(job_name="ghost", command="run_now", requested_at=datetime.now(timezone.utc), requested_by="admin:fan", state="pending"))
        db.commit()
    poller.poll()
    assert scheduler.jobs["fetch_list"].next_run_time is not None
    with factory() as db:
        states = {c.job_name: (c.state, c.note) for c in db.query(CronJobCommandDB)}
    assert states["fetch_list"][0] == "done" and states["ghost"][0] == "rejected" and states["ghost"][1]


def test_run_now_on_a_paused_job_is_rejected_by_cron_too(factory):
    recorder, scheduler = setup(factory), FakeScheduler(["fetch_list"])
    with factory() as db:
        db.add(CronJobControlDB(job_name="fetch_list", paused=True, reason="上游维护中", changed_at=datetime.now(timezone.utc), changed_by="admin:fan"))
        db.add(CronJobCommandDB(job_name="fetch_list", command="run_now", requested_at=datetime.now(timezone.utc), requested_by="admin:fan", state="pending"))
        db.commit()
    ControlPoller(factory, recorder, scheduler).poll()
    assert scheduler.jobs["fetch_list"].next_run_time is None
    with factory() as db:
        assert db.query(CronJobCommandDB).one().state == "rejected"


def test_a_missing_control_table_does_not_break_the_poller():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    poller = ControlPoller(sessionmaker(bind=engine), RunRecorder(sessionmaker(bind=engine)), FakeScheduler([]))
    assert poller.poll() is False


def test_a_failed_poll_preserves_the_last_known_pause_snapshot(factory):
    recorder = setup(factory)
    with factory() as db:
        db.add(
            CronJobControlDB(
                job_name="fetch_list", paused=True, reason="上游维护中",
                changed_at=datetime.now(timezone.utc), changed_by="admin:fan",
            )
        )
        db.commit()
    poller = ControlPoller(factory, recorder, FakeScheduler(["fetch_list"]))
    assert poller.poll(False)

    def unavailable():
        raise RuntimeError("controls unavailable")

    poller.session_factory = unavailable
    assert poller.poll(False) is False
    assert recorder.paused == {"fetch_list": "上游维护中"}


@pytest.mark.parametrize("failures", [6, 8])
def test_startup_waits_for_controls_then_honours_the_persisted_pause(factory, monkeypatch, failures):
    from katrain.cron import controls
    from katrain.cron.scheduler import CronScheduler

    class SchedulerStarted(Exception):
        pass

    async def inline(func, *args):
        return func(*args)

    async def no_sleep(seconds):
        pass

    async def scenario():
        scheduler = CronScheduler()
        scheduler._recorder = RunRecorder(factory)
        attempts = 0
        with factory() as db:
            db.add(
                CronJobControlDB(
                    job_name="fetch_list", paused=True, reason="上游维护中",
                    changed_at=datetime.now(timezone.utc), changed_by="admin:fan",
                )
            )
            db.commit()

        def recovering_factory():
            nonlocal attempts
            attempts += 1
            if attempts <= failures:
                raise RuntimeError("controls unavailable")
            return factory()

        def started():
            assert attempts == failures + 1  # interval execution must wait until pause state is known
            raise SchedulerStarted

        monkeypatch.setattr(
            controls, "ControlPoller", lambda _, recorder, aps: ControlPoller(recovering_factory, recorder, aps)
        )
        monkeypatch.setattr(controls, "POLL_S", 0)
        monkeypatch.setattr(asyncio, "to_thread", inline)
        monkeypatch.setattr(asyncio, "sleep", no_sleep)
        monkeypatch.setattr(scheduler._scheduler, "start", started)
        with pytest.raises(SchedulerStarted):
            await scheduler.start()
        assert scheduler._recorder.paused == {"fetch_list": "上游维护中"}
        paused, unpaused = Job("fetch_list"), Job("poll_moves")
        scheduler._schedule(paused, 60)
        scheduler._schedule(unpaused, 3)
        for job in scheduler._scheduler.get_jobs():
            await job.func(*job.args)
        assert paused.calls == 0 and unpaused.calls == 1

    asyncio.run(scenario())


def test_shutdown_while_waiting_for_initial_controls_does_not_start_scheduler(factory, monkeypatch):
    from katrain.cron import controls
    from katrain.cron.scheduler import CronScheduler

    async def inline(func, *args):
        return func(*args)

    async def scenario():
        scheduler = CronScheduler()
        scheduler._recorder = RunRecorder(factory)
        entered, started = asyncio.Event(), []

        def unavailable(self, commands=True):
            entered.set()
            return False

        monkeypatch.setattr(controls.ControlPoller, "poll", unavailable)
        monkeypatch.setattr(asyncio, "to_thread", inline)
        monkeypatch.setattr(scheduler._scheduler, "start", lambda: started.append(True))
        task = asyncio.create_task(scheduler.start())
        try:
            await asyncio.wait_for(entered.wait(), timeout=1)
            await scheduler.shutdown()
            await asyncio.wait_for(task, timeout=1)
            assert started == []
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def test_web_and_cron_map_identical_control_tables():
    for web, cron in ((models_db.CronJobControl, CronJobControlDB), (models_db.CronJobCommand, CronJobCommandDB)):
        shape = lambda m: {c.name: (str(c.type), c.nullable, c.primary_key) for c in m.__table__.columns}  # noqa: E731
        assert web.__tablename__ == cron.__tablename__ and shape(web) == shape(cron)


def test_run_now_is_refused_while_the_job_is_running_and_stale_commands_expire(factory):
    from datetime import timedelta

    recorder, scheduler = setup(factory), FakeScheduler(["fetch_list"])
    poller = ControlPoller(factory, recorder, scheduler)
    recorder.running.add("fetch_list")
    with factory() as db:
        db.add(CronJobCommandDB(job_name="fetch_list", command="run_now", requested_at=datetime.now(timezone.utc), requested_by="admin:fan", state="pending"))
        db.add(CronJobCommandDB(job_name="fetch_list", command="run_now", requested_at=poller.started_at - timedelta(minutes=1), requested_by="admin:fan", state="pending"))
        db.commit()
    poller.poll()
    assert scheduler.jobs["fetch_list"].next_run_time is None
    with factory() as db:
        notes = [c.note for c in db.query(CronJobCommandDB).order_by(CronJobCommandDB.id)]
    assert "正在运行" in notes[0] and "已过期" in notes[1]
