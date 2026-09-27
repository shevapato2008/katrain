"""Box telemetry: trust-on-first-use registration, admin approval, signed and replay-proof heartbeats."""

import hashlib
import hmac
import json
import secrets
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.core import device_telemetry
from katrain.web.core.models_db import Base, BoxDevice

SECRET = "factory-secret-" + "x" * 20


def derived(secret=SECRET):
    return hmac.new(secret.encode(), device_telemetry.KEY_CONTEXT, hashlib.sha256).hexdigest()


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    from katrain.web.api.v1.endpoints import devices

    app = FastAPI()
    app.state.session_factory = factory
    clock = {"now": 1_800_000_000.0}
    app.state.device_clock = lambda: clock["now"]
    app.include_router(devices.router, prefix="/api/v1/devices")
    return TestClient(app), factory, clock


def register(client, device_id="sbx-0001", key=None):
    return client.post("/api/v1/devices/register", json={"device_id": device_id, "key": key or derived(), "board": "rk3562"})


def beat(client, clock, device_id="sbx-0001", key=None, ts=None, body=None, signature=None):
    payload = json.dumps(body or {"board": "rk3562", "smartbox_version": "1.4.2", "katrain_build": "a41c9e2", "mode": "go", "uptime_s": 3600}).encode()
    stamp = str(int(ts if ts is not None else clock["now"]))
    sig = signature or hmac.new(bytes.fromhex(key or derived()), stamp.encode() + b"\n" + payload, hashlib.sha256).hexdigest()
    return client.post(
        "/api/v1/devices/heartbeat",
        content=payload,
        headers={"Content-Type": "application/json", "X-Device-Id": device_id, "X-Device-Timestamp": stamp, "X-Device-Signature": sig},
    )


def approve(factory, device_id="sbx-0001"):
    with factory() as db:
        db.get(BoxDevice, device_id).status = "approved"
        db.commit()


def test_first_registration_is_pending_and_the_same_key_is_idempotent(env):
    client, factory, _ = env
    first = register(client)
    assert first.status_code == 200 and first.json()["status"] == "pending"
    assert register(client).json()["status"] == "pending"
    assert register(client, key=derived("another-secret-xxxxxxxxxxxxxxxxxx")).status_code == 409
    with factory() as db:
        row = db.get(BoxDevice, "sbx-0001")
    assert row.status == "pending" and row.key == derived()


def test_a_signed_heartbeat_updates_the_device_and_a_forged_one_does_not(env):
    client, factory, clock = env
    register(client)
    ok = beat(client, clock)
    assert ok.status_code == 200 and ok.json()["status"] == "pending"
    with factory() as db:
        row = db.get(BoxDevice, "sbx-0001")
        assert row.smartbox_version == "1.4.2" and row.katrain_build == "a41c9e2" and row.last_seen is not None
    clock["now"] += 300
    assert beat(client, clock, key=derived("forged-secret-xxxxxxxxxxxxxxxxxx")).status_code == 401
    assert beat(client, clock, device_id="sbx-unknown").status_code == 401


def test_replays_and_stale_clocks_are_refused_with_the_server_time(env):
    client, factory, clock = env
    register(client)
    assert beat(client, clock).status_code == 200
    assert beat(client, clock).status_code == 401  # same timestamp again = replay
    skewed = beat(client, clock, ts=clock["now"] + 301)
    assert skewed.status_code == 401 and skewed.json()["detail"]["code"] == "clock_skew"
    assert skewed.json()["detail"]["server_time"] == int(clock["now"])


def test_rejected_devices_are_refused(env):
    client, factory, clock = env
    register(client)
    with factory() as db:
        db.get(BoxDevice, "sbx-0001").status = "rejected"
        db.commit()
    assert beat(client, clock).status_code == 403
    assert register(client).status_code == 403


def test_pending_registrations_are_capped_and_expire(env):
    client, factory, clock = env
    for index in range(device_telemetry.MAX_PENDING):
        assert register(client, device_id=f"sbx-{index:04d}", key=secrets.token_hex(32)).status_code == 200
    assert register(client, device_id="sbx-over", key=secrets.token_hex(32)).status_code == 429
    clock["now"] += 8 * 86400
    assert register(client, device_id="sbx-over", key=secrets.token_hex(32)).status_code == 200
    with factory() as db:
        assert len(db.scalars(select(BoxDevice)).all()) == 1


@pytest.mark.parametrize("payload", [
    {"device_id": "bad id!", "key": "0" * 64},
    {"device_id": "sbx-1", "key": "short"},
    {"device_id": "sbx-1", "key": "g" * 64},
])
def test_registration_input_is_validated(env, payload):
    client, _, _ = env
    assert client.post("/api/v1/devices/register", json=payload).status_code == 422


def test_heartbeat_fields_are_bounded(env):
    client, factory, clock = env
    register(client)
    approve(factory)
    big = {"board": "b" * 500, "smartbox_version": "v", "katrain_build": "k", "mode": "go", "uptime_s": 1}
    assert beat(client, clock, body=big).status_code == 422


@pytest.fixture
def admin(monkeypatch, tmp_path, env):
    from passlib.context import CryptContext

    from katrain.web.admin.app import create_admin_app

    _, factory, _ = env
    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", CryptContext(schemes=["bcrypt"]).hash("local-only-password"))
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    client = TestClient(create_admin_app(session_factory=factory, static_dir=tmp_path))
    token = client.post("/api/admin/auth/login", json={"username": "admin:fan", "password": "local-only-password"})
    return client, {"Authorization": f"Bearer {token.json()['access_token']}"}


def test_admin_approves_pending_devices_with_audit_and_sees_honest_states(env, admin):
    from datetime import datetime, timedelta, timezone

    from katrain.web.core.models_db import AdminAuditLog

    box, factory, clock = env
    client, headers = admin
    register(box, "sbx-a")
    register(box, "sbx-b", key=secrets.token_hex(32))
    register(box, "sbx-c", key=secrets.token_hex(32))
    assert client.get("/api/admin/devices").status_code == 401
    assert client.post("/api/admin/devices/sbx-a/approve", headers=headers).json()["status"] == "approved"
    assert client.post("/api/admin/devices/sbx-a/approve", headers=headers).status_code == 409
    assert client.post("/api/admin/devices/sbx-b/reject", headers=headers).json()["status"] == "rejected"
    assert client.post("/api/admin/devices/nope/approve", headers=headers).status_code == 404
    listing = client.get("/api/admin/devices", headers=headers).json()
    assert {d["device_id"]: d["state"] for d in listing["devices"]} == {"sbx-a": "never", "sbx-b": "rejected", "sbx-c": "pending"}
    with factory() as db:
        db.get(BoxDevice, "sbx-a").last_seen = datetime.now(timezone.utc) - timedelta(minutes=20)
        db.commit()
    assert {d["device_id"]: d["state"] for d in client.get("/api/admin/devices", headers=headers).json()["devices"]}["sbx-a"] == "offline"
    with factory() as db:
        actions = [a.action for a in db.scalars(select(AdminAuditLog).where(AdminAuditLog.target_type == "box_device")).all()]
    assert sorted(actions) == ["device_approve", "device_reject"]
    assert "key" not in listing["devices"][0]
