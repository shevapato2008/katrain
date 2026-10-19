import copy
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from katrain.web.kifu import player_existing17 as existing


def test_created_at_padding_is_semantic_only():
    assert existing._equal({"created_at": "2026-09-30T19:51:59.38943+00:00"},
                           {"created_at": "2026-09-30T19:51:59.389430+00:00"})
    assert not existing._equal({"created_at": "2026-09-30T19:51:59.389431+00:00"},
                               {"created_at": "2026-09-30T19:51:59.38943+00:00"})
    assert not existing._equal({"origin_path": "changed.sgf"}, {"origin_path": "same.sgf"})


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_pinned_decision_and_exact_event_rebase_capture(environment, monkeypatch):
    frozen, decision, approved, held, deltas = existing.evidence(environment)
    assert (len(approved), len(held), len(deltas)) == (3576, 807, 137)
    snapshot = {key: copy.deepcopy(frozen[key]) for key in existing.TABLES}
    snapshot["event_catalog"] = copy.deepcopy(
        decision["intervening_six_league_rebase"]["environments"][environment]["target_catalog_rows"])
    snapshot["albums"] = copy.deepcopy(frozen["albums"])
    snapshot["null_slots"] = sorted([r["album_id"], r["side"], r["raw"]] for r in frozen["slots"])
    by_id = {row["id"]: row for row in snapshot["albums"]}
    for album_id, event_id in deltas.items():
        by_id[album_id]["event_id"] = event_id
    monkeypatch.setattr(existing, "_snapshot", lambda db, source: snapshot)
    db = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    plan = existing._capture(db, frozen, decision, approved, held, deltas, environment)
    assert plan["counts"] == {"approved": 3576, "held": 807}
    held_slot = held[0]
    assert by_id[held_slot["album_id"]][held_slot["side"] + "_player_id"] is None
    changed = next(iter(deltas))
    by_id[changed]["event_id"] = 999999
    with pytest.raises(ValueError, match="event_id"):
        existing._capture(db, frozen, decision, approved, held, deltas, environment)


def test_decision_rejects_changed_approved_target():
    frozen, decision, approved, held, _ = existing.evidence("prod")
    damaged = copy.deepcopy(decision)
    damaged["approved_slots"][0]["target_ids"]["prod"] = 999999
    with pytest.raises(ValueError, match="slot hash"):
        existing._member_sets(damaged, frozen, "prod")


@pytest.mark.parametrize("opposite_path", [
    "docs/resource/kifu-player-existing17-prod-full-readonly-2026-10-04.json.gz",
    "docs/resource/kifu-event-six-leagues-PROD-applied-plan-2026-10-04.json.gz",
])
def test_test_evidence_rejects_mutated_opposite_environment_file(monkeypatch, opposite_path):
    original_read = Path.read_bytes
    target = existing.ROOT / opposite_path

    def read_bytes(path):
        data = original_read(path)
        return data + b"changed" if path == target else data

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    with pytest.raises(ValueError, match="pinned evidence SHA differs"):
        existing.evidence("test")


def test_transaction_rollback_commit_and_cas(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'existing17.db'}")
    with engine.begin() as db:
        db.execute(text("CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, player_black TEXT, date_played TEXT, black_player_id INTEGER)"))
        db.execute(text("INSERT INTO kifu_albums VALUES (1,'raw','2026-01-01',NULL)"))
    approved = [{"album_id": 1, "side": "black", "raw": "raw", "date_played": "2026-01-01",
                 "target_ids": {"test": 42}}]
    plan = {"format": "kifu-player-existing17-exact-plan-v1", "environment": "test",
            "database": "katrain_db", "snapshot": {"albums": [{"id": 1, "black_player_id": None}],
                                                 "null_slots": [[1, "black", "raw"]]},
            "counts": {"approved": 1, "held": 0}}
    monkeypatch.setattr(existing, "evidence", lambda environment: ({}, {}, approved, [], {}))
    monkeypatch.setattr(existing, "_capture", lambda *args: plan)

    def snapshot(db, frozen):
        row = db.execute(text("SELECT id,black_player_id FROM kifu_albums WHERE id=1")).mappings().one()
        return {"albums": [dict(row)], "null_slots": [[1, "black", "raw"]] if row["black_player_id"] is None else []}
    monkeypatch.setattr(existing, "_snapshot", snapshot)
    assert existing.run(engine, "test", plan)["committed"] is False
    with engine.connect() as db:
        assert db.scalar(text("SELECT black_player_id FROM kifu_albums")) is None
    assert existing.run(engine, "test", plan, apply=True, plan_sha256="reviewed",
                        approved_plan_sha256="reviewed")["committed"] is True
    with engine.connect() as db:
        assert db.scalar(text("SELECT black_player_id FROM kifu_albums")) == 42
    with pytest.raises(ValueError, match="CAS failed"):
        existing.run(engine, "test", plan)
