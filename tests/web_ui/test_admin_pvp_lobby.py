"""The admin process reads central PvP state through the shared database."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.core.models_db import AdminAuditLog, AiLadderProfile, Base, SystemConfigDB, User
from katrain.web.core.pvp_lobby_bots import playable_rungs


@pytest.fixture
def setup():
    from katrain.web.admin.routers import pvp_lobby
    from katrain.web.admin.session import get_current_admin

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.state.session_factory = factory
    from katrain.web.admin.settings import AdminConfig
    app.state.admin_config = AdminConfig("admin:fan", "", "test-secret", "test")
    app.include_router(pvp_lobby.router, prefix="/api/admin")
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, app, factory, get_current_admin
    engine.dispose()


def authorize(app, dependency):
    app.dependency_overrides[dependency] = lambda: {"realm": "admin", "username": "admin:fan"}


def config(**changes):
    return {"version": 1, "enabled": False, "bot_game_limit": 3, "idle_targets": {}, **changes}


def snapshot(factory, *, age=0, participants=(), **changes):
    value = {
        "reported_at": (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat(),
        "applied_config_revision": 0,
        "active_bot_games": 1,
        "engine_errors": 0,
        "rungs": [{"rung": rung.rung, "rank_label": rung.rank_label, "idle_now": 2, "playing_now": 0} for rung in playable_rungs()],
        "participants": list(participants),
        **changes,
    }
    with factory() as db:
        db.merge(SystemConfigDB(key="pvp_lobby_bot_runtime", value=json.dumps(value)))
        db.commit()


def test_admin_only_reads_and_writes(setup):
    client, app, _, dependency = setup
    assert client.get("/api/admin/pvp-lobby").status_code == 401
    assert client.get("/api/admin/pvp-lobby/participants").status_code == 401
    assert client.put("/api/admin/pvp-lobby/config", json={"expected_revision": 0, "config": config()}).status_code == 401
    authorize(app, dependency)
    assert client.get("/api/admin/pvp-lobby").status_code == 200


def test_validates_limits_and_complete_catalog(setup):
    client, app, factory, dependency = setup
    authorize(app, dependency)
    for bad in (
        config(bot_game_limit=7), config(bot_game_limit=-1), config(idle_targets={"1": 0}),
        config(idle_targets={"1": 21}), config(idle_targets={"999": 2}),
    ):
        assert client.put("/api/admin/pvp-lobby/config", json={"expected_revision": 0, "config": bad}).status_code == 422
    assert client.put("/api/admin/pvp-lobby/config", json={"expected_revision": 0, "config": config(), "extra": True}).status_code == 422
    saved = client.put("/api/admin/pvp-lobby/config", json={"expected_revision": 0, "config": config()})
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["config_revision"] == 1
    assert len(body["config"]["idle_targets"]) == len(playable_rungs()) == 29
    assert set(body["config"]["idle_targets"].values()) == {2}
    with factory() as db:
        assert db.scalar(select(AdminAuditLog).where(AdminAuditLog.action == "pvp_lobby_config_update")) is not None


def test_conflict_and_atomic_audit_rollback(setup, monkeypatch):
    client, app, factory, dependency = setup
    authorize(app, dependency)
    assert client.put("/api/admin/pvp-lobby/config", json={"expected_revision": 0, "config": config()}).status_code == 200
    assert client.put("/api/admin/pvp-lobby/config", json={"expected_revision": 0, "config": config(enabled=True)}).status_code == 409
    with factory() as db:
        assert db.scalar(select(AdminAuditLog).where(AdminAuditLog.action == "pvp_lobby_config_update")) is not None
    original_commit = Session.commit
    def fail_audit(self):
        if any(isinstance(row, AdminAuditLog) for row in self.new):
            raise RuntimeError("audit unavailable")
        return original_commit(self)
    monkeypatch.setattr(Session, "commit", fail_audit)
    assert client.put("/api/admin/pvp-lobby/config", json={"expected_revision": 1, "config": config(enabled=True)}).status_code == 500
    assert client.get("/api/admin/pvp-lobby").json()["config_revision"] == 1


def test_runtime_missing_stale_and_applied_revision(setup):
    client, app, factory, dependency = setup
    authorize(app, dependency)
    missing = client.get("/api/admin/pvp-lobby").json()
    assert missing["runtime"]["stale"] is True
    assert missing["runtime"]["reported_at"] is None
    snapshot(factory, age=60)
    assert client.get("/api/admin/pvp-lobby").json()["runtime"]["stale"] is True
    snapshot(factory)
    current = client.get("/api/admin/pvp-lobby").json()
    assert current["runtime"]["stale"] is False
    assert current["runtime"]["rungs"][0]["idle_target"] == 2
    assert current["runtime"]["applied_config_revision"] == 0


def test_paged_complete_roster_with_filters(setup):
    client, app, factory, dependency = setup
    authorize(app, dependency)
    with factory() as db:
        for n in range(1, 5):
            db.add(User(id=n, username=f"human-{n}", hashed_password="secret"))
        db.flush()
        db.add(AiLadderProfile(user_id=1, ai_ladder_rung=1, placement_lo=1, placement_hi=1))
        db.commit()
    snapshot(factory, participants=[
        {"id": 1, "username": "human-1", "kind": "human", "ladder_rung": 1, "rank_label": playable_rungs()[0].rank_label, "presence": "idle"},
        {"id": -1, "username": "bot-1", "kind": "bot", "ladder_rung": 1, "rank_label": playable_rungs()[0].rank_label, "presence": "idle"},
        {"id": -2, "username": "bot-2", "kind": "bot", "ladder_rung": 1, "rank_label": playable_rungs()[0].rank_label, "presence": "playing"},
    ])
    url = "/api/admin/pvp-lobby/participants"
    first = client.get(url, params={"page": 1, "page_size": 2}).json()
    second = client.get(url, params={"page": 2, "page_size": 2}).json()
    third = client.get(url, params={"page": 3, "page_size": 2}).json()
    assert first["total"] == 6
    assert [row["id"] for part in (first, second, third) for row in part["items"]] == [1, 2, 3, 4, -1, -2]
    assert first["items"][0]["rank_label"] == playable_rungs()[0].rank_label
    assert first["items"][1]["presence"] == "offline"
    assert client.get(url, params={"kind": "bot", "presence": "playing"}).json()["total"] == 1
    assert client.get(url, params={"kind": "human", "presence": "online", "q": "human"}).json()["total"] == 1
    humans = client.get(url, params={"kind": "human", "page_size": 100}).json()
    assert humans["total"] == 4
    assert [row["kind"] for row in humans["items"]] == ["human"] * 4
    assert client.get(url, params={"page_size": 200}).json()["page_size"] == 100


def test_stale_snapshot_does_not_claim_participants_are_current(setup):
    client, app, factory, dependency = setup
    authorize(app, dependency)
    with factory() as db:
        db.add(User(id=1, username="human-1", hashed_password="secret"))
        db.commit()
    snapshot(factory, age=60, participants=[
        {"id": 1, "username": "human-1", "kind": "human", "ladder_rung": 1, "rank_label": "20级", "presence": "idle"},
        {"id": -1, "username": "bot-1", "kind": "bot", "ladder_rung": 1, "rank_label": "20级", "presence": "playing"},
    ])
    url = "/api/admin/pvp-lobby/participants"
    assert client.get(url, params={"presence": "online"}).json()["total"] == 0
    assert client.get(url, params={"presence": "offline"}).json()["total"] == 0
    all_rows = client.get(url, params={"presence": "all"}).json()["items"]
    assert [(row["kind"], row["presence"]) for row in all_rows] == [("human", "unknown"), ("bot", "unknown")]
