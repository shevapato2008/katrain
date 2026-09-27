"""Error tracking: a bounded, non-blocking logging collector that groups ERROR records by fingerprint."""

import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.core import error_collector
from katrain.web.core.models_db import AdminAuditLog, Base, ErrorGroup


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def record(message="boom %s", args=("x",), logger="katrain.web.games", exc=None, line=10, func="play"):
    exc_info = None
    if exc is not None:
        try:
            raise exc
        except Exception as caught:  # noqa: BLE001
            exc_info = (type(caught), caught, caught.__traceback__)
    return logging.LogRecord(logger, logging.ERROR, "/app/katrain/web/games.py", line, message, args, exc_info, func)


def groups(factory):
    with factory() as db:
        return db.scalars(select(ErrorGroup).order_by(ErrorGroup.id)).all()


def test_same_template_groups_regardless_of_arguments_and_line(factory):
    collector = error_collector.ErrorCollector("web", factory)
    collector.emit(record(args=("a",), line=10))
    collector.emit(record(args=("b",), line=99))
    collector.emit(record(message="other failure %s"))
    assert collector.flush() is True
    rows = groups(factory)
    assert [(r.template, r.count) for r in rows] == [("boom %s", 2), ("other failure %s", 1)]
    assert rows[0].sample.startswith("boom b")  # the latest sample is kept


def test_exception_type_and_frames_are_part_of_the_fingerprint(factory):
    collector = error_collector.ErrorCollector("web", factory)
    collector.emit(record(exc=ValueError("bad")))
    collector.emit(record(exc=KeyError("bad")))
    collector.flush()
    rows = groups(factory)
    assert {r.exc_type for r in rows} == {"ValueError", "KeyError"} and len(rows) == 2
    assert all("test_admin_error_tracking.py:record" in r.location for r in rows)


def test_samples_are_scrubbed_and_capped(factory):
    collector = error_collector.ErrorCollector("web", factory)
    secret = "call 13812345678 mail a.b@example.com Bearer abc.def token=s3cr3t password=hunter2 jwt eyJhbGciOi.eyJzdWIi.sig"
    collector.emit(record(message="%s", args=(secret + " " + "x" * 9000,)))
    collector.flush()
    sample = groups(factory)[0].sample
    for leaked in ("13812345678", "a.b@example.com", "abc.def", "s3cr3t", "hunter2", "eyJhbGciOi"):
        assert leaked not in sample
    assert len(sample) <= 4096


def test_emit_never_blocks_or_raises_and_counts_drops(factory):
    collector = error_collector.ErrorCollector("web", factory, max_queue=2)
    for _ in range(5):
        collector.emit(record())
    assert collector.stats()["collector"]["dropped"] == 3 and collector.stats()["collector"]["queued"] == 2


def test_the_collectors_own_logger_is_ignored(factory):
    collector = error_collector.ErrorCollector("web", factory)
    collector.emit(record(logger=error_collector.LOGGER_NAME))
    assert collector.stats()["collector"]["queued"] == 0


def test_a_failing_database_is_absorbed_and_reported(factory):
    def broken():
        raise RuntimeError("db down")

    collector = error_collector.ErrorCollector("web", broken)
    collector.emit(record())
    assert collector.flush() is False
    stats = collector.stats()["collector"]
    assert stats["dropped"] == 1 and stats["last_flush_ok"] is False


def test_resolved_groups_reopen_when_they_recur(factory):
    collector = error_collector.ErrorCollector("web", factory)
    collector.emit(record())
    collector.flush()
    with factory() as db:
        row = db.scalars(select(ErrorGroup)).one()
        row.resolved_at, row.resolved_by = datetime.now(timezone.utc), "admin:fan"
        db.commit()
    collector.emit(record())
    collector.flush()
    row = groups(factory)[0]
    assert row.resolved_at is None and row.count == 2


def test_group_cap_and_retention(factory):
    collector = error_collector.ErrorCollector("web", factory, max_groups=2)
    for index in range(3):
        collector.emit(record(message=f"distinct {index}"))
    collector.flush()
    assert len(groups(factory)) == 2 and collector.stats()["collector"]["overflow"] == 1
    with factory() as db:
        old = db.scalars(select(ErrorGroup)).first()
        old.last_seen = datetime.now(timezone.utc) - timedelta(days=31)
        db.commit()
    collector.prune(force=True)
    assert len(groups(factory)) == 1


def test_cron_copy_computes_the_same_fingerprint_and_tags_the_job():
    from katrain.cron import error_collector as cron_collector
    from katrain.cron import run_recorder

    rec = record(exc=ValueError("bad"))
    assert cron_collector.fingerprint("cron", rec) == error_collector.fingerprint("cron", rec)
    token = run_recorder.current_job.set("report_analyze")
    try:
        event = cron_collector.ErrorCollector(lambda: None)._event(rec)
    finally:
        run_recorder.current_job.reset(token)
    assert event["job"] == "report_analyze"


def test_web_and_cron_map_the_same_error_table():
    from katrain.cron.models import ErrorGroupDB

    shape = lambda model: {c.name: (str(c.type), c.nullable, c.primary_key, bool(c.unique)) for c in model.__table__.columns}  # noqa: E731
    assert ErrorGroup.__tablename__ == ErrorGroupDB.__tablename__ and shape(ErrorGroup) == shape(ErrorGroupDB)


@pytest.fixture
def admin(monkeypatch, tmp_path, factory):
    from katrain.web.admin.app import create_admin_app

    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", CryptContext(schemes=["bcrypt"]).hash("local-only-password"))
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    client = TestClient(create_admin_app(session_factory=factory, static_dir=tmp_path))
    token = client.post("/api/admin/auth/login", json={"username": "admin:fan", "password": "local-only-password"})
    return client, {"Authorization": f"Bearer {token.json()['access_token']}"}


def test_admin_lists_resolves_with_audit_and_counts_attention(admin, factory):
    client, headers = admin
    collector = error_collector.ErrorCollector("web", factory)
    collector.emit(record())
    collector.emit(record(message="cron side %s", logger="katrain_cron.jobs"))
    collector.flush()
    assert client.get("/api/admin/errors").status_code == 401
    listing = client.get("/api/admin/errors?status=open", headers=headers).json()
    assert listing["total"] == 2 and {"count", "sample", "location", "first_seen"} <= set(listing["items"][0])
    assert client.get("/api/admin/attention", headers=headers).json()["errors"] == 2
    target = listing["items"][0]["id"]
    assert client.post(f"/api/admin/errors/{target}/resolve", headers=headers).status_code == 200
    assert client.get("/api/admin/errors?status=open", headers=headers).json()["total"] == 1
    assert client.get("/api/admin/errors?status=resolved", headers=headers).json()["items"][0]["resolved_by"] == "admin:fan"
    with factory() as db:
        audit = db.scalars(select(AdminAuditLog).where(AdminAuditLog.action == "error_resolve")).one()
    assert audit.target_type == "error_group" and audit.target_id == target
    assert client.get("/api/admin/attention", headers=headers).json()["errors"] == 1
    assert client.post("/api/admin/errors/9999/resolve", headers=headers).status_code == 404
