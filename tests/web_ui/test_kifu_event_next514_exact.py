import copy
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from katrain.web.kifu import event_next514_exact as next514


def _frozen(environment):
    path, sha = next514.FROZEN[environment]
    return next514._pinned(path, sha)


def test_both_next3_catalog_rebases_are_exact():
    for environment in ("test", "prod"):
        next514._validate_next3_catalog_rebase(
            environment, next514._pinned(*next514.PRE_NEXT3[environment]),
            _frozen(environment), next514._pinned(*next514.NEXT3_PLAN[environment]))


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_final_decision_exact_partition_and_full_capture(environment, monkeypatch):
    decision, frozen, sha = next514.evidence(environment)
    assert (len(decision["approved"]), len(decision["held"])) == (474, 40)
    snapshot = {key: copy.deepcopy(frozen[key]) for key in
                ("albums", "album_sources", "sources", "events", "aliases", "editions", "players")}
    monkeypatch.setattr(next514, "_snapshot", lambda db, album_ids, player_ids: snapshot)
    db = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    plan = next514._capture(db, decision, frozen, environment, sha)
    assert plan["counts"] == {"approved": 474, "held": 40}
    held_id = decision["held_ids"][0]
    held_album = next(row for row in snapshot["albums"] if row["id"] == held_id)
    held_album["event_id"] = 999999
    with pytest.raises(ValueError, match="frozen albums"):
        next514._capture(db, decision, frozen, environment, sha)


def test_full_frozen_capture_guards_hold_and_ancillary(monkeypatch):
    frozen = _frozen("test")
    ids = [row["id"] for row in frozen["albums"]]
    decision = {"approved_ids": ids[:-1], "held_ids": ids[-1:],
                "targets": {"existing": {"id": 75, "canonical_name": "中日围棋对抗赛", "family_key": "china_japan"},
                            "create": [{"family_key": "bawang", "canonical_name": "测试全新甲赛事"},
                                       {"family_key": "xintiyu", "canonical_name": "测试全新乙赛事"}]}}
    snapshot = {key: copy.deepcopy(frozen[key]) for key in
                ("albums", "album_sources", "sources", "events", "aliases", "editions", "players")}
    monkeypatch.setattr(next514, "_snapshot", lambda db, album_ids, player_ids: snapshot)
    db = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    plan = next514._capture(db, decision, frozen, "test", "pinned")
    assert plan["counts"] == {"approved": 513, "held": 1}
    snapshot["albums"][-1]["event_id"] = 999999
    with pytest.raises(ValueError, match="frozen albums"):
        next514._capture(db, decision, frozen, "test", "pinned")
    snapshot["albums"][-1]["event_id"] = None
    snapshot["album_sources"][0]["origin_path"] = "different.sgf"
    with pytest.raises(ValueError, match="album_sources"):
        next514._capture(db, decision, frozen, "test", "pinned")


def test_dry_rollback_commit_and_cas(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'next514.db'}")
    with engine.begin() as db:
        db.execute(text("CREATE TABLE kifu_events (id INTEGER PRIMARY KEY, canonical_name TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"))
        db.execute(text("CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, event TEXT, date_played TEXT, event_id INTEGER, event_edition_id INTEGER)"))
        db.execute(text("INSERT INTO kifu_events VALUES (75,'existing',CURRENT_TIMESTAMP)"))
        db.execute(text("INSERT INTO kifu_albums VALUES (1,'raw','2020-01-01',NULL,NULL)"))
    decision = {"approved": [{"id": 1, "raw_preimage": {"event": "raw", "date_played": "2020-01-01"},
                               "family_key": "new_a"}],
                "approved_ids": [1], "held_ids": [],
                "targets": {"existing": {"id": 75, "canonical_name": "existing", "family_key": "old"},
                            "create": [{"family_key": "new_a", "canonical_name": "new a"},
                                       {"family_key": "new_b", "canonical_name": "new b"}]}}
    with engine.connect() as db:
        before_events = [dict(row) for row in db.execute(text("SELECT id,canonical_name,created_at FROM kifu_events")).mappings()]
    plan = {"format": "kifu-event-next514-exact-plan-v1", "environment": "test", "database": "katrain_db",
            "snapshot": {"albums": [{"id": 1, "event_id": None}], "events": before_events, "players": []},
            "counts": {"approved": 1, "held": 0}}
    monkeypatch.setattr(next514, "evidence", lambda environment: (decision, {}, "pinned"))
    monkeypatch.setattr(next514, "_capture", lambda *args: plan)

    def snapshot(db, ids, player_ids):
        return {"albums": [dict(row) for row in db.execute(text("SELECT id,event_id FROM kifu_albums")).mappings()],
                "events": [dict(row) for row in db.execute(text("SELECT id,canonical_name,created_at FROM kifu_events ORDER BY id")).mappings()],
                "players": []}
    monkeypatch.setattr(next514, "_snapshot", snapshot)
    assert next514.run(engine, "test", plan)["committed"] is False
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM kifu_events")) == 1
    result = next514.run(engine, "test", plan, apply=True, plan_sha256="reviewed", approved_plan_sha256="reviewed")
    assert result["committed"] is True
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM kifu_events")) == 3
        inserted = [dict(row) for row in db.execute(text("SELECT id,canonical_name,created_at FROM kifu_events WHERE id!=75 ORDER BY id")).mappings()]
    with engine.begin() as db:
        db.execute(text("UPDATE kifu_events SET created_at='changed' WHERE id=:id"),
                   {"id": result["created_event_ids"]["new_a"]})
    with pytest.raises(ValueError, match="posttransaction full scope"):
        next514._verify_final(engine, decision, plan, result["created_event_ids"], inserted, True)
    with pytest.raises(ValueError, match="CAS failed"):
        next514.run(engine, "test", plan)
