import copy
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from katrain.web.kifu import event_next3_exact as next3


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_pinned_scope_capture_and_player_rebase(environment, monkeypatch):
    decision, frozen, changes = next3.evidence(environment)
    assert (len(decision["approved"]), len(decision["held"]), len(changes)) == (2153, 268, 27)
    snapshot = {key: copy.deepcopy(frozen[key]) for key in
                ("albums", "album_sources", "sources", "catalog", "aliases", "editions")}
    albums = {row["id"]: row for row in snapshot["albums"]}
    for change in changes:
        albums[change["album_id"]] = copy.deepcopy(change["_expected_album"])
    snapshot["albums"] = sorted(albums.values(), key=lambda row: row["id"])
    overlap = {change["album_id"] for change in changes}
    snapshot["album_sources"] = [row for row in snapshot["album_sources"] if row["album_id"] not in overlap]
    snapshot["album_sources"] += [copy.deepcopy(row) for change in changes for row in change["_expected_sources"]]
    snapshot["album_sources"].sort(key=lambda row: row["id"])
    snapshot["player_catalog"] = sorted({change["new"]: copy.deepcopy(change["target_catalog_row"])
                                          for change in changes}.values(), key=lambda row: row["id"])
    monkeypatch.setattr(next3, "_snapshot", lambda db, ids, target_ids: snapshot)
    db = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    plan = next3._capture(db, decision, frozen, changes, environment)
    assert plan["counts"] == {"approved": 2153, "held": 268, "player_rebased": 27}
    held_album = decision["held"][0]["id"]
    albums[held_album]["event_id"] = 999999
    with pytest.raises(ValueError, match="NULL event/edition"):
        next3._capture(db, decision, frozen, changes, environment)
    albums[held_album]["event_id"] = None
    changed = changes[0]
    albums[changed["album_id"]][changed["column"]] = 999999
    with pytest.raises(ValueError, match="player postimage"):
        next3._capture(db, decision, frozen, changes, environment)


def test_test_overlap_rejects_other_fk_source_and_target_drift(monkeypatch):
    decision, frozen, changes = next3.evidence("test")
    change = changes[0]
    snapshot = {key: copy.deepcopy(frozen[key]) for key in
                ("albums", "album_sources", "sources", "catalog", "aliases", "editions")}
    albums = {row["id"]: row for row in snapshot["albums"]}
    for item in changes:
        albums[item["album_id"]] = copy.deepcopy(item["_expected_album"])
    snapshot["albums"] = sorted(albums.values(), key=lambda row: row["id"])
    overlap = {item["album_id"] for item in changes}
    snapshot["album_sources"] = [row for row in snapshot["album_sources"] if row["album_id"] not in overlap]
    snapshot["album_sources"] += [copy.deepcopy(row) for item in changes for row in item["_expected_sources"]]
    snapshot["album_sources"].sort(key=lambda row: row["id"])
    snapshot["player_catalog"] = sorted({item["new"]: copy.deepcopy(item["target_catalog_row"])
                                          for item in changes}.values(), key=lambda row: row["id"])
    monkeypatch.setattr(next3, "_snapshot", lambda db, ids, target_ids: snapshot)
    db = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    next3._capture(db, decision, frozen, changes, "test")
    album = albums[change["album_id"]]
    other_fk = "black_player_id" if change["column"] == "white_player_id" else "white_player_id"
    before = album[other_fk]
    album[other_fk] = 999999
    with pytest.raises(ValueError, match="complete player postimage"):
        next3._capture(db, decision, frozen, changes, "test")
    album[other_fk] = before
    association = next(row for row in snapshot["album_sources"] if row["album_id"] == change["album_id"])
    association["origin_path"] = "wrong.sgf"
    with pytest.raises(ValueError, match="source association"):
        next3._capture(db, decision, frozen, changes, "test")
    association["origin_path"] = change["_expected_sources"][0]["origin_path"]
    target = next(row for row in snapshot["player_catalog"] if row["id"] == change["new"])
    target["canonical_name"] = "wrong person"
    with pytest.raises(ValueError, match="player target catalog"):
        next3._capture(db, decision, frozen, changes, "test")


def test_created_at_padding_and_duplicate_catalog_guard():
    assert next3._equal({"created_at": "2026-10-04T08:11:04.07699+00:00"},
                        {"created_at": "2026-10-04T08:11:04.076990+00:00"})
    assert not next3._equal({"created_at": "2026-10-04T08:11:04.076991+00:00"},
                            {"created_at": "2026-10-04T08:11:04.07699+00:00"})
    with pytest.raises(ValueError, match="collides"):
        next3._catalog_guard({"catalog": [], "aliases": [{"alias": "臺灣聯電盃職業圍棋賽",
                                                           "normalized_alias": "臺灣聯電盃職業圍棋賽"}]})


def test_dry_rollback_commit_and_cas(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'next3.db'}")
    with engine.begin() as db:
        db.execute(text("CREATE TABLE kifu_events (id INTEGER PRIMARY KEY, canonical_name TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"))
        db.execute(text("CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, event TEXT, date_played TEXT, event_id INTEGER, event_edition_id INTEGER)"))
        db.execute(text("INSERT INTO kifu_albums VALUES (1,'raw','2020-01-01',NULL,NULL)"))
    decision = {"approved": [{"id": 1, "event": "raw", "date_played": "2020-01-01",
                               "family_key": "tw_youshi_tendan"}], "approved_ids": [1], "held_ids": []}
    plan = {"format": "kifu-event-next3-exact-plan-v1", "environment": "test", "database": "katrain_db",
            "snapshot": {"albums": [{"id": 1, "event_id": None}], "catalog": [], "player_catalog": []},
            "counts": {"approved": 1, "held": 0, "player_rebased": 0}}
    monkeypatch.setattr(next3, "evidence", lambda environment: (decision, {}, []))
    monkeypatch.setattr(next3, "_capture", lambda *args: plan)

    def snapshot(db, ids, target_ids):
        return {"albums": [dict(row) for row in db.execute(text("SELECT id,event_id FROM kifu_albums")).mappings()],
                "catalog": [dict(row) for row in db.execute(text("SELECT id,canonical_name,created_at FROM kifu_events ORDER BY id")).mappings()],
                "player_catalog": []}
    monkeypatch.setattr(next3, "_snapshot", snapshot)
    assert next3.run(engine, "test", plan)["committed"] is False
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM kifu_events")) == 0
        assert db.scalar(text("SELECT event_id FROM kifu_albums")) is None
    result = next3.run(engine, "test", plan, apply=True, plan_sha256="reviewed", approved_plan_sha256="reviewed")
    assert result["committed"] is True and len(result["created_event_ids"]) == 3
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM kifu_events")) == 3
        inserted = [dict(row) for row in db.execute(text("SELECT id,canonical_name,created_at FROM kifu_events ORDER BY id")).mappings()]
    with engine.begin() as db:
        db.execute(text("UPDATE kifu_events SET created_at='changed' WHERE id=:id"),
                   {"id": result["created_event_ids"]["tw_youshi_tendan"]})
    with pytest.raises(ValueError, match="posttransaction full scope"):
        next3._verify_final(engine, plan, decision, result["created_event_ids"], True, inserted)
    with pytest.raises(ValueError, match="CAS failed"):
        next3.run(engine, "test", plan)
