"""Config check: each process writes templated verdicts (never values) about its own effective config."""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.core import health_report
from katrain.web.core.models_db import Base, ProcessHealthReport

SENTINEL = "SENTINELpw9x7q"


def web_settings(**overrides):
    base = dict(
        DATABASE_URL=f"postgresql://katrain_user:{SENTINEL}@db:5432/katrain_db",
        KATRAIN_MODE="server",
        BILLING_ENFORCED=False,
        FREE_WEEKLY_REPORTS=1,
        CLOUD_KATAGO_URL=f"http://gpu.internal:8000/?token={SENTINEL}",
        STORAGE_BACKEND="s3",
        S3_SECRET_KEY=SENTINEL,
    )
    return SimpleNamespace(**{**base, **overrides})


def levels(checks):
    return {c["id"]: c["level"] for c in checks}


def test_healthy_web_config_is_all_ok_or_explained():
    checks = health_report.web_checks(web_settings())
    assert levels(checks) == {"database": "ok", "mode": "ok", "billing": "ok", "cloud_katago": "ok", "storage": "ok", "credentials": "ok"}
    assert "免费" in next(c["message"] for c in checks if c["id"] == "billing")


@pytest.mark.parametrize(
    "overrides, check, level",
    [
        ({"DATABASE_URL": "sqlite:///./db.sqlite3"}, "database", "bad"),
        ({"KATRAIN_MODE": "board"}, "mode", "bad"),
        ({"BILLING_ENFORCED": True, "FREE_WEEKLY_REPORTS": 1}, "billing", "bad"),
        ({"BILLING_ENFORCED": True, "FREE_WEEKLY_REPORTS": 0}, "billing", "ok"),
        ({"CLOUD_KATAGO_URL": ""}, "cloud_katago", "warn"),
        ({"STORAGE_BACKEND": "local"}, "storage", "warn"),
        ({"DATABASE_URL": "postgresql://u:katrain_secure_password_CHANGE_ME@db/k"}, "credentials", "bad"),
        ({"S3_SECRET_KEY": "minio_secure_password_CHANGE_ME"}, "credentials", "bad"),
    ],
)
def test_each_web_rule(overrides, check, level):
    assert levels(health_report.web_checks(web_settings(**overrides)))[check] == level


def test_a_check_that_raises_is_unknown_not_ok():
    broken = SimpleNamespace(KATRAIN_MODE="server")  # every other attribute missing
    checks = health_report.web_checks(broken)
    assert levels(checks)["database"] == "unknown" and levels(checks)["mode"] == "ok"


def test_reports_never_carry_config_values(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setenv("KATRAIN_BUILD_SHA", "abc1234")
    health_report.write_report(factory, "web", health_report.web_checks(web_settings(STORAGE_BACKEND="local")))
    health_report.write_report(factory, "web", health_report.web_checks(web_settings()))
    with factory() as db:
        rows = db.query(ProcessHealthReport).all()
    assert len(rows) == 1 and rows[0].build == "abc1234" and rows[0].process == "web"
    assert SENTINEL not in rows[0].report and levels(json.loads(rows[0].report)["checks"])["storage"] == "ok"


def test_cron_checks_live_in_the_cron_package_and_leak_nothing(monkeypatch):
    from katrain.cron import health_report as cron_report

    config = SimpleNamespace(DATABASE_URL=f"postgresql://u:{SENTINEL}@db/k", KATAGO_URL="", DASHSCOPE_API_KEY="")
    checks = cron_report.cron_checks(config)
    assert levels(checks) == {"database": "ok", "katago": "bad", "translation": "warn", "credentials": "ok"}
    assert SENTINEL not in json.dumps(checks, ensure_ascii=False)
    assert levels(cron_report.cron_checks(SimpleNamespace(DATABASE_URL="sqlite:///x", KATAGO_URL="http://k", DASHSCOPE_API_KEY="k")))["database"] == "bad"


def test_web_and_cron_map_the_same_report_table():
    from katrain.cron.models import ProcessHealthReportDB

    web = {c.name: (str(c.type), c.nullable, c.primary_key) for c in ProcessHealthReport.__table__.columns}
    cron = {c.name: (str(c.type), c.nullable, c.primary_key) for c in ProcessHealthReportDB.__table__.columns}
    assert ProcessHealthReport.__tablename__ == ProcessHealthReportDB.__tablename__ and web == cron


@pytest.fixture
def admin(monkeypatch, tmp_path):
    from katrain.web.admin.app import create_admin_app

    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", CryptContext(schemes=["bcrypt"]).hash("local-only-password"))
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    client = TestClient(create_admin_app(session_factory=factory, static_dir=tmp_path))
    token = client.post("/api/admin/auth/login", json={"username": "admin:fan", "password": "local-only-password"})
    return client, {"Authorization": f"Bearer {token.json()['access_token']}"}, factory


def put(factory, process, build, age_minutes, checks=None):
    with factory() as db:
        db.merge(
            ProcessHealthReport(
                process=process,
                hostname="host-1",
                build=build,
                generated_at=datetime.now(timezone.utc) - timedelta(minutes=age_minutes),
                report=json.dumps({"checks": checks or [{"id": "database", "level": "ok", "message": "PostgreSQL"}]}),
            )
        )
        db.commit()


def test_admin_view_distinguishes_never_stale_and_fresh(admin):
    client, headers, factory = admin
    assert client.get("/api/admin/config-health").status_code == 401
    put(factory, "web", "abc1234", 2)
    put(factory, "cron", "abc1234", 45)
    body = client.get("/api/admin/config-health", headers=headers).json()
    states = {p["process"]: p["state"] for p in body["processes"]}
    assert states == {"web": "fresh", "cron": "stale", "admin": states["admin"]}
    cron = next(p for p in body["processes"] if p["process"] == "cron")
    assert cron["checks"] == [] and cron["generated_at"]  # stale verdicts are withheld, the time is kept
    version = next(c for c in body["cross_checks"] if c["id"] == "build_consistency")
    assert version["level"] == "unknown"  # only fresh reports count; cron is stale


def test_build_consistency_across_fresh_reports(admin):
    client, headers, factory = admin
    for process in ("web", "cron", "admin"):
        put(factory, process, "abc1234", 1)
    same = client.get("/api/admin/config-health", headers=headers).json()
    assert next(c for c in same["cross_checks"] if c["id"] == "build_consistency")["level"] == "ok"
    put(factory, "cron", "def5678", 1)
    differ = client.get("/api/admin/config-health", headers=headers).json()
    assert next(c for c in differ["cross_checks"] if c["id"] == "build_consistency")["level"] == "warn"
    put(factory, "cron", "unknown", 1)
    unknown = client.get("/api/admin/config-health", headers=headers).json()
    assert next(c for c in unknown["cross_checks"] if c["id"] == "build_consistency")["level"] == "unknown"


def test_a_process_that_never_reported_is_bad(admin):
    client, headers, factory = admin
    body = client.get("/api/admin/config-health", headers=headers).json()
    web = next(p for p in body["processes"] if p["process"] == "web")
    assert web["state"] == "never" and web["generated_at"] is None
