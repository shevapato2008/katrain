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
        assert db.get(CronJobStatusDB, "fetch_list").last_status == "paused"
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
    with factory() as db:
        db.add(CronJobCommandDB(job_name="fetch_list", command="run_now", requested_at=datetime.now(timezone.utc), requested_by="admin:fan", state="pending"))
        db.add(CronJobCommandDB(job_name="ghost", command="run_now", requested_at=datetime.now(timezone.utc), requested_by="admin:fan", state="pending"))
        db.commit()
    ControlPoller(factory, recorder, scheduler).poll()
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


def test_web_and_cron_map_identical_control_tables():
    for web, cron in ((models_db.CronJobControl, CronJobControlDB), (models_db.CronJobCommand, CronJobCommandDB)):
        shape = lambda m: {c.name: (str(c.type), c.nullable, c.primary_key) for c in m.__table__.columns}  # noqa: E731
        assert web.__tablename__ == cron.__tablename__ and shape(web) == shape(cron)
