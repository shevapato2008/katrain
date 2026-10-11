import copy

import pytest
from sqlalchemy import create_engine, text

from katrain.web.core.models_db import KifuPlayer
from katrain.web.kifu import player_new33_firstbatch as batch


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_pinned_exact_evidence_and_event_only_rebase(environment):
    frozen, decision, supplement, expected = batch.evidence(environment)
    assert len(decision["approved_slots"]) == 1451
    assert len(decision["held_slots"]) == 5922
    assert len(expected["albums"]) == 7168
    assert len(expected["slots"]) == 7373
    assert len(expected["events"]) == 77
    assert len(expected["event_editions"]) == 1535
    changed = supplement["exact_album_rebases"][environment][0]
    original = next(row for row in frozen[environment]["albums"] if row["id"] == changed["album_id"])
    current = next(row for row in expected["albums"] if row["id"] == changed["album_id"])
    assert {key for key in current if original[key] != current[key]} == {"event_id"}
    damaged = copy.deepcopy(expected)
    next(row for row in damaged["albums"] if row["id"] == changed["album_id"])["event"] = "changed"
    with pytest.raises(ValueError, match="album"):
        batch.validate_snapshot(damaged, expected, decision, environment)
    damaged = copy.deepcopy(expected)
    damaged["events"][0]["canonical_name"] = "unexpected global catalog drift"
    with pytest.raises(ValueError, match="events"):
        batch.validate_snapshot(damaged, expected, decision, environment)


def test_hold_slot_cannot_be_released():
    _, decision, _, expected = batch.evidence("test")
    damaged = copy.deepcopy(expected)
    held = decision["held_slots"][0]
    album = next(row for row in damaged["albums"] if row["id"] == held["album_id"])
    album[held["side"] + "_player_id"] = 42
    with pytest.raises(ValueError, match="album"):
        batch.validate_snapshot(damaged, expected, decision, "test")


def test_frozen_referenced_event_must_match_pinned_global_plan(monkeypatch):
    original_pin = batch._pin

    def altered_plan(path, sha):
        value = original_pin(path, sha)
        if path.endswith("kifu-event-next3-TEST-applied-plan-2026-10-04.json.gz"):
            value = copy.deepcopy(value)
            value["snapshot"]["catalog"][0]["canonical_name"] = "changed in global plan"
        return value

    monkeypatch.setattr(batch, "_pin", altered_plan)
    with pytest.raises(ValueError, match="frozen referenced event catalog"):
        batch.evidence("test")


def test_postimage_preserves_held_slot_and_updates_its_opponent_fk():
    plan = {"snapshot": {"albums": [{"id": 1, "black_player_id": None, "white_player_id": None}],
                         "slots": [{"album_id": 1, "side": "black", "opponent_fk": None},
                                   {"album_id": 1, "side": "white", "opponent_fk": None}],
                         "catalog": {"players": []}}}
    approved = [{"album_id": 1, "side": "black", "raw": "批准"}]
    after = batch._after(plan, approved, {"批准": 42}, [])
    assert after["albums"][0] == {"id": 1, "black_player_id": 42, "white_player_id": None}
    assert after["slots"] == [{"album_id": 1, "side": "white", "opponent_fk": 42}]
    assert plan["snapshot"]["slots"][1]["opponent_fk"] is None


def test_apply_requires_separately_approved_plan_sha():
    with pytest.raises(ValueError, match="separately approved"):
        batch.run(None, "test", {}, apply=True, plan_sha256="captured")


def test_transaction_dry_rollback_then_apply_and_independent_reread(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'new33.db'}")
    KifuPlayer.__table__.create(engine)
    with engine.begin() as db:
        db.execute(text("CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, player_black TEXT NOT NULL, "
                        "player_white TEXT NOT NULL, date_played TEXT, black_player_id INTEGER, white_player_id INTEGER)"))
        db.execute(text("INSERT INTO kifu_players(id,canonical_name) VALUES (50,'本田寿子')"))
        db.execute(text("INSERT INTO kifu_albums VALUES (1,'新棋手','对手','2020-01-01',NULL,NULL)"))
    snapshot = {"albums": [{"id": 1, "black_player_id": None, "white_player_id": None}],
                "slots": [{"album_id": 1, "side": "black", "opponent_fk": None}],
                "catalog": {"players": [{"id": 50, "canonical_name": "本田寿子"}]}}
    plan = {"format": batch.FORMAT, "environment": "test", "database": "katrain_db",
            "decision_sha256": batch.DECISION_SHA, "supplement_sha256": batch.SUPPLEMENT_SHA,
            "snapshot": snapshot, "counts": {"approved": 1, "held": 0}}
    identities = [{"raw": f"新棋手{i}", "chinese_canonical": f"新棋手{i}",
                   "target_ids": {"test": None}} for i in range(7)]
    identities[0]["raw"] = "新棋手"
    decision = {"identities": identities + [{"raw": "杉内寿子", "target_ids": {"test": 50}}],
                "approved_slots": [{"album_id": 1, "side": "black", "raw": "新棋手",
                                    "date_played": "2020-01-01"}]}
    monkeypatch.setattr(batch, "evidence", lambda environment: ({"test": {}}, decision, {}, {}))
    monkeypatch.setattr(batch, "_capture", lambda *args: plan)

    def live_snapshot(db, frozen, expected):
        album = db.execute(text("SELECT id,black_player_id,white_player_id FROM kifu_albums")).mappings().one()
        players = [dict(row) for row in db.execute(text("SELECT id,canonical_name FROM kifu_players ORDER BY id")).mappings()]
        return {"albums": [dict(album)], "slots": snapshot["slots"] if album["black_player_id"] is None else [],
                "catalog": {"players": players}}

    monkeypatch.setattr(batch, "_snapshot", live_snapshot)
    assert batch.run(engine, "test", plan)["committed"] is False
    with engine.connect() as db:
        assert db.scalar(text("SELECT black_player_id FROM kifu_albums")) is None
        assert db.scalar(text("SELECT count(*) FROM kifu_players")) == 1
    assert batch.run(engine, "test", plan, apply=True, plan_sha256="reviewed",
                     approved_plan_sha256="reviewed")["committed"] is True
    with engine.connect() as db:
        assert db.scalar(text("SELECT black_player_id FROM kifu_albums")) is not None
        assert db.scalar(text("SELECT count(*) FROM kifu_players")) == 8
