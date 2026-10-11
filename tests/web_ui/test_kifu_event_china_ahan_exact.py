import copy
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from katrain.web.kifu import event_china_ahan_exact as ahan


def _fake_db():
    return SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_pinned_capture_and_exact_player_rebase(environment, monkeypatch):
    decision, frozen, sha, rebase = ahan.evidence(environment)
    assert (len(decision["approved"]), len(decision["held"])) == (793, 8)
    assert len(decision["prior_hold_union_ids"]) == 4265
    snapshot = {key: copy.deepcopy(frozen[key]) for key in ahan.SNAPSHOT_KEYS}
    snapshot["albums"] = copy.deepcopy(rebase[0])
    snapshot["new33_target_players"] = [
        {"id": id_, "canonical_name": name, "created_at": "2026-10-04T12:00:00+00:00"}
        for name, id_ in sorted(rebase[1].items(), key=lambda item: item[1])]
    monkeypatch.setattr(ahan, "_snapshot", lambda *args: snapshot)
    plan = ahan._capture(_fake_db(), decision, frozen, environment, sha, rebase)
    assert plan["counts"] == {"approved": 793, "held": 8, "prior_held": 4265}
    overlap_id = next(row["id"] for row in frozen["albums"] if row != rebase[0][frozen["albums"].index(row)])
    changed = next(row for row in snapshot["albums"] if row["id"] == overlap_id)
    field = "black_player_id" if changed["black_player_id"] != next(x for x in frozen["albums"] if x["id"] == overlap_id)["black_player_id"] else "white_player_id"
    changed[field] = 999999
    with pytest.raises(ValueError, match="frozen albums"):
        ahan._capture(_fake_db(), decision, frozen, environment, sha, rebase)
    changed[field] = next(x for x in rebase[0] if x["id"] == overlap_id)[field]
    snapshot["prior_hold_event_slots"][0]["event_id"] = 79
    with pytest.raises(ValueError, match="prior_hold_event_slots"):
        ahan._capture(_fake_db(), decision, frozen, environment, sha, rebase)
    snapshot["prior_hold_event_slots"][0]["event_id"] = None
    snapshot["album_sources"][0]["origin_path"] = "wrong.sgf"
    with pytest.raises(ValueError, match="album_sources"):
        ahan._capture(_fake_db(), decision, frozen, environment, sha, rebase)


def test_transaction_dry_apply_cas_and_independent_read(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ahan.db'}")
    with engine.begin() as db:
        db.execute(text("CREATE TABLE kifu_events (id INTEGER PRIMARY KEY, canonical_name TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"))
        db.execute(text("CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, event TEXT, date_played TEXT, event_id INTEGER, event_edition_id INTEGER)"))
        db.execute(text("INSERT INTO kifu_albums VALUES (1,'raw','2020-01-01',NULL,NULL)"))
        db.execute(text("INSERT INTO kifu_albums VALUES (2,'hold','2020-01-01',NULL,NULL)"))
    decision = {"approved": [{"id": 1, "raw_preimage": {"event": "raw", "date_played": "2020-01-01"}}],
                "approved_ids": [1], "held_ids": [2], "prior_hold_union_ids": []}
    plan = {"format": "kifu-event-china-ahan-exact-plan-v1", "environment": "test", "database": "katrain_db",
            "snapshot": {"albums": [{"id": 1, "event_id": None}, {"id": 2, "event_id": None}],
                         "events": [], "players": [], "new33_target_players": [], "prior_hold_event_slots": []},
            "counts": {"approved": 1, "held": 1, "prior_held": 0}}
    monkeypatch.setattr(ahan, "evidence", lambda environment: (decision, {}, "sha", ([], {})))
    monkeypatch.setattr(ahan, "_capture", lambda *args: plan)

    def snapshot(db, *args):
        return {"albums": [dict(row) for row in db.execute(text("SELECT id,event_id FROM kifu_albums ORDER BY id")).mappings()],
                "events": [dict(row) for row in db.execute(text("SELECT id,canonical_name,created_at FROM kifu_events ORDER BY id")).mappings()],
                "players": [], "new33_target_players": [], "prior_hold_event_slots": []}
    monkeypatch.setattr(ahan, "_snapshot", snapshot)
    assert ahan.run(engine, "test", plan)["committed"] is False
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM kifu_events")) == 0
    result = ahan.run(engine, "test", plan, apply=True, plan_sha256="approved", approved_plan_sha256="approved")
    assert result["committed"] is True
    with engine.connect() as db:
        assert db.scalar(text("SELECT event_id FROM kifu_albums WHERE id=2")) is None
        inserted = dict(db.execute(text("SELECT id,canonical_name,created_at FROM kifu_events")).mappings().one())
    with engine.begin() as db:
        db.execute(text("UPDATE kifu_events SET created_at='changed' WHERE id=:id"), {"id": inserted["id"]})
    with pytest.raises(ValueError, match="posttransaction full scope"):
        ahan._verify_final(engine, decision, plan, inserted["id"], inserted, True)
    with pytest.raises(ValueError, match="CAS failed"):
        ahan.run(engine, "test", plan)
