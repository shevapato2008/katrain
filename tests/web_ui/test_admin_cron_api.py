"""Read-only cron status, history, and queue endpoints on the dedicated admin app."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import OperationalError

from katrain.web.admin.app import create_admin_app
from katrain.web.admin.session import create_session_token
from katrain.web.core.models_db import CronJobRun, CronJobStatus, LiveAnalysisDB, ReportTask


@pytest.fixture
def admin_client(monkeypatch, tmp_path):
    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", "$2b$12$" + "a" * 53)
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    monkeypatch.setenv("KATRAIN_SECRET_KEY", "p" * 48)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    for model in (CronJobStatus, CronJobRun, LiveAnalysisDB, ReportTask):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    client = TestClient(create_admin_app(session_factory=factory, static_dir=tmp_path))
    token = create_session_token("admin:fan", "test")
    yield client, factory, engine, {"Authorization": f"Bearer {token}"}
    engine.dispose()


def test_all_cron_endpoints_require_admin_session(admin_client):
    client, _, _, _ = admin_client
    for path in ("/api/admin/cron/jobs", "/api/admin/cron/jobs/fetch_list/runs", "/api/admin/cron/queues"):
        assert client.get(path).status_code == 401


def test_jobs_include_current_health_and_aware_timestamps(admin_client):
    client, factory, _, auth = admin_client
    now = datetime.now(timezone.utc)
    with factory() as db:
        db.add_all(
            [
                CronJobStatus(
                    job_name="fetch_list",
                    kind="interval",
                    interval_seconds=60,
                    enabled=True,
                    process_started_at=now - timedelta(hours=1),
                    heartbeat_at=now - timedelta(seconds=10),
                    last_started_at=now - timedelta(seconds=20),
                    last_status="success",
                    consecutive_failures=0,
                ),
                CronJobStatus(
                    job_name="analyze",
                    kind="loop",
                    enabled=True,
                    heartbeat_at=now - timedelta(seconds=10),
                    last_status="running",
                    loop_iteration_at=now - timedelta(seconds=3),
                    loop_stats={"in_flight": 2, "capacity": 16, "errors_total": 0, "last_error_at": None},
                    consecutive_failures=0,
                ),
            ]
        )
        db.commit()

    response = client.get("/api/admin/cron/jobs", headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert datetime.fromisoformat(body["observed_at"]).tzinfo is not None
    assert [job["name"] for job in body["jobs"]] == ["analyze", "fetch_list"]
    by_name = {job["name"]: job for job in body["jobs"]}
    assert by_name["fetch_list"]["health"]["state"] == "ok"
    assert by_name["analyze"]["health"]["state"] == "ok"
    assert by_name["analyze"]["loop_stats"]["in_flight"] == 2
    assert by_name["analyze"]["process_started_at"] is None
    assert datetime.fromisoformat(by_name["fetch_list"]["heartbeat_at"]).utcoffset() == timedelta(0)
    assert set(by_name["fetch_list"]) == {
        "name",
        "kind",
        "interval_seconds",
        "enabled",
        "health",
        "process_started_at",
        "heartbeat_at",
        "last_started_at",
        "last_finished_at",
        "last_success_at",
        "last_status",
        "last_duration_ms",
        "last_error",
        "consecutive_failures",
        "loop_iteration_at",
        "loop_stats",
    }


def test_missing_status_table_returns_503(admin_client):
    client, _, engine, auth = admin_client
    CronJobStatus.__table__.drop(engine)
    response = client.get("/api/admin/cron/jobs", headers=auth)
    assert response.status_code == 503
    assert response.json() == {"detail": "cron 状态表不存在：katrain-web 新版本还没启动过"}


def test_missing_runs_table_reports_that_table(admin_client):
    client, factory, engine, auth = admin_client
    with factory() as db:
        db.add(CronJobStatus(job_name="fetch_list", kind="interval", interval_seconds=60, enabled=True))
        db.commit()
    CronJobRun.__table__.drop(engine)

    response = client.get("/api/admin/cron/jobs/fetch_list/runs", headers=auth)
    assert response.status_code == 503
    assert response.json() == {"detail": "cron 运行记录表不存在：katrain-web 新版本还没启动过"}


def test_database_outage_is_not_reported_as_missing_table(admin_client):
    client, _, _, auth = admin_client

    def unavailable():
        raise OperationalError("connect", {}, OSError("connection refused"))

    client.app.state.session_factory = unavailable
    for path in ("/api/admin/cron/jobs", "/api/admin/cron/jobs/fetch_list/runs", "/api/admin/cron/queues"):
        response = client.get(path, headers=auth)
        assert response.status_code == 503
        assert response.json() == {"detail": "cron 数据库暂时不可用"}


def test_runs_are_newest_first_paginated_and_limited_to_200(admin_client):
    client, factory, _, auth = admin_client
    now = datetime.now(timezone.utc)
    with factory() as db:
        db.add(CronJobStatus(job_name="fetch_list", kind="interval", interval_seconds=60, enabled=True))
        db.add_all(
            CronJobRun(
                job_name="fetch_list",
                started_at=now - timedelta(minutes=i),
                status="errors",
                error_count=2,
                error="first ERROR",
            )
            for i in range(60)
        )
        db.commit()

    first = client.get("/api/admin/cron/jobs/fetch_list/runs", headers=auth)
    assert first.status_code == 200
    first_body = first.json()
    ids = [run["id"] for run in first_body["runs"]]
    assert len(ids) == 50 and ids == sorted(ids, reverse=True)
    assert first_body["next_before_id"] == ids[-1]
    assert first_body["runs"][0]["error_count"] == 2
    assert datetime.fromisoformat(first_body["runs"][0]["started_at"]).tzinfo is not None

    second = client.get(f"/api/admin/cron/jobs/fetch_list/runs?before_id={ids[-1]}", headers=auth)
    assert second.status_code == 200
    assert len(second.json()["runs"]) == 10
    assert second.json()["next_before_id"] is None
    assert len(client.get("/api/admin/cron/jobs/fetch_list/runs?limit=200", headers=auth).json()["runs"]) == 60
    assert client.get("/api/admin/cron/jobs/fetch_list/runs?limit=201", headers=auth).status_code == 422
    assert client.get("/api/admin/cron/jobs/unknown/runs", headers=auth).status_code == 404


def test_queues_count_statuses_and_oldest_pending(admin_client):
    client, factory, _, auth = admin_client
    now = datetime.now(timezone.utc)
    with factory() as db:
        db.add_all(
            [
                LiveAnalysisDB(match_id="m1", move_number=1, status="pending", created_at=now - timedelta(minutes=3)),
                LiveAnalysisDB(match_id="m1", move_number=2, status="success", created_at=now),
                ReportTask(user_id=1, user_game_id="g1", status="pending", created_at=now - timedelta(minutes=5)),
                ReportTask(user_id=1, user_game_id="g2", status="pending", created_at=now - timedelta(minutes=2)),
                ReportTask(user_id=1, user_game_id="g3", status="completed", created_at=now),
            ]
        )
        db.commit()

    response = client.get("/api/admin/cron/queues", headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert datetime.fromisoformat(body["observed_at"]).tzinfo is not None
    assert body["report_tasks"]["by_status"] == {"pending": 2, "completed": 1}
    oldest = datetime.fromisoformat(body["report_tasks"]["oldest_pending_at"])
    assert abs((oldest - (now - timedelta(minutes=5))).total_seconds()) < 1
    assert body["live_analysis"]["by_status"] == {"pending": 1, "success": 1}
    live_oldest = datetime.fromisoformat(body["live_analysis"]["oldest_pending_at"])
    assert abs((live_oldest - (now - timedelta(minutes=3))).total_seconds()) < 1
