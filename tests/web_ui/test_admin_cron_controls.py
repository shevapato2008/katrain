"""Admin cron controls: pause / resume / run now, each audited in the same transaction."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.admin.app import create_admin_app
from katrain.web.admin.session import create_session_token
from katrain.web.core.models_db import AdminAuditLog, Base, CronJobCommand, CronJobControl, CronJobStatus


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", "$2b$12$" + "a" * 53)
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    monkeypatch.setenv("KATRAIN_SECRET_KEY", "p" * 48)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    now = datetime.now(timezone.utc)
    with factory() as db:
        for name, kind, interval, enabled in (("fetch_list", "interval", 60, True), ("analyze", "loop", None, True), ("translate", "interval", 300, False)):
            db.add(CronJobStatus(job_name=name, kind=kind, interval_seconds=interval, enabled=enabled, heartbeat_at=now - timedelta(seconds=5), last_started_at=now - timedelta(seconds=20), last_status="success", consecutive_failures=0, loop_iteration_at=now))
        db.commit()
    client = TestClient(create_admin_app(session_factory=factory, static_dir=tmp_path))
    return client, factory, {"Authorization": f"Bearer {create_session_token('admin:fan', 'test')}"}


def post(client, auth, name, action, **body):
    return client.post(f"/api/admin/cron/jobs/{name}/{action}", headers=auth, json=body or None)


def actions(factory):
    with factory() as db:
        return [a.action for a in db.scalars(select(AdminAuditLog).where(AdminAuditLog.target_type == "cron_job").order_by(AdminAuditLog.id))]


def test_controls_require_the_admin_session(env):
    client, _, _ = env
    for action in ("pause", "resume", "run"):
        assert client.post(f"/api/admin/cron/jobs/fetch_list/{action}").status_code == 401


def test_pause_shows_in_health_and_resume_clears_it(env):
    client, factory, auth = env
    assert post(client, auth, "fetch_list", "pause", reason="短").status_code == 422
    assert post(client, auth, "fetch_list", "pause", reason="上游接口维护中").status_code == 200
    job = next(j for j in client.get("/api/admin/cron/jobs", headers=auth).json()["jobs"] if j["name"] == "fetch_list")
    assert job["health"]["state"] == "paused" and "上游接口维护中" in job["health"]["reason"] and job["paused"] is True
    assert post(client, auth, "fetch_list", "pause", reason="上游接口维护中").status_code == 409
    assert post(client, auth, "fetch_list", "resume").status_code == 200
    job = next(j for j in client.get("/api/admin/cron/jobs", headers=auth).json()["jobs"] if j["name"] == "fetch_list")
    assert job["paused"] is False and job["health"]["state"] != "paused"
    assert actions(factory) == ["cron_pause", "cron_resume"]


def test_run_now_queues_one_command_and_refuses_what_cron_cannot_do(env):
    client, factory, auth = env
    queued = post(client, auth, "fetch_list", "run")
    assert queued.status_code == 200 and queued.json()["state"] == "pending"
    assert post(client, auth, "fetch_list", "run").status_code == 409  # one pending at a time
    assert post(client, auth, "analyze", "run").status_code == 409  # loop jobs run continuously
    assert post(client, auth, "analyze", "pause", reason="上游接口维护中").status_code == 409
    assert post(client, auth, "translate", "run").status_code == 409  # disabled by config
    assert post(client, auth, "nope", "run").status_code == 404
    job = next(j for j in client.get("/api/admin/cron/jobs", headers=auth).json()["jobs"] if j["name"] == "fetch_list")
    assert job["pending_run"]["requested_by"] == "admin:fan"
    with factory() as db:
        assert db.query(CronJobCommand).count() == 1
    post(client, auth, "fetch_list", "pause", reason="上游接口维护中")
    with factory() as db:
        db.query(CronJobCommand).update({"state": "done"})
        db.commit()
    assert post(client, auth, "fetch_list", "run").status_code == 409  # paused
    assert actions(factory) == ["cron_run_now", "cron_pause"]


def test_a_resumed_job_is_not_overdue_for_the_time_it_was_paused(env):
    client, factory, auth = env
    with factory() as db:
        row = db.get(CronJobStatus, "fetch_list")
        row.last_started_at = datetime.now(timezone.utc) - timedelta(days=2)
        db.commit()
    post(client, auth, "fetch_list", "pause", reason="上游接口维护中")
    post(client, auth, "fetch_list", "resume")
    job = next(j for j in client.get("/api/admin/cron/jobs", headers=auth).json()["jobs"] if j["name"] == "fetch_list")
    assert job["health"]["state"] == "ok"
