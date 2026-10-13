import copy

import pytest
from sqlalchemy import create_engine, text

from katrain.web.core.models_db import KifuPlayer
from katrain.web.kifu import player_new33_secondbatch as batch


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_pinned_committed_rebase_and_full_scope(environment):
    frozen, decision, rebase, expected = batch.evidence(environment)
    assert len(frozen[environment]["albums"]) == 7168
    assert len(decision["approved_slots"]) == 2755
    assert len(decision["held_slots"]) == 543
    assert len(decision["excluded_slots"]) == 4075
    assert len(expected["albums"]) == 7168
    assert len(expected["slots"]) == 5922
    assert len(expected["catalog"]["players"]) == len(frozen[environment]["catalog"]["players"]) + 7
    assert len(expected["events"]) == 79
    assert len(expected["event_editions"]) == 1535
    batch.validate_snapshot(copy.deepcopy(expected), expected)
    damaged = copy.deepcopy(expected)
    damaged["albums"][0]["event_id"] = 999999
    with pytest.raises(ValueError, match="albums"):
        batch.validate_snapshot(damaged, expected)


def test_global_event_catalog_drift_fails():
    _, _, _, expected = batch.evidence("test")
    damaged = copy.deepcopy(expected)
    damaged["events"][0]["canonical_name"] = "unexpected"
    with pytest.raises(ValueError, match="events"):
        batch.validate_snapshot(damaged, expected)


def test_apply_requires_separate_plan_sha():
    with pytest.raises(ValueError, match="separately approved"):
        batch.run(None, "test", {}, apply=True, plan_sha256="plan")


def test_transaction_dry_rollback_then_apply_and_independent_reread(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'new33_second.db'}")
    KifuPlayer.__table__.create(engine)
    with engine.begin() as db:
        db.execute(text("CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, player_black TEXT NOT NULL, "
                        "player_white TEXT NOT NULL, date_played TEXT, black_player_id INTEGER, white_player_id INTEGER)"))
        db.execute(text("INSERT INTO kifu_players(id,canonical_name) VALUES (50,'既有')"))
        db.execute(text("INSERT INTO kifu_albums VALUES (1,'新棋手0','对手','2020-01-01',NULL,NULL)"))
    snapshot = {"albums": [{"id": 1, "black_player_id": None, "white_player_id": None}],
                "slots": [{"album_id": 1, "side": "black", "opponent_fk": None}],
                "catalog": {"players": [{"id": 50, "canonical_name": "既有"}]}}
    plan = {"format": batch.FORMAT, "environment": "test", "database": "katrain_db",
            "decision_sha256": batch.DECISION_SHA, "rebase_sha256": batch.REBASE_SHA,
            "snapshot": snapshot, "counts": {"approved": 1, "held": 0}}
    identities = [{"raw": f"新棋手{i}", "chinese_canonical": f"新棋手{i}", "target_ids": {"test": None}}
                  for i in range(16)]
    decision = {"identities": identities, "approved_slots": [
        {"album_id": 1, "side": "black", "raw": "新棋手0", "date_played": "2020-01-01"}]}
    monkeypatch.setattr(batch, "evidence", lambda environment: ({"test": {}}, decision, {}, {}))
    monkeypatch.setattr(batch, "_capture", lambda *args: plan)

    def live_snapshot(db, frozen, expected):
        album = db.execute(text("SELECT id,black_player_id,white_player_id FROM kifu_albums")).mappings().one()
        players = [dict(row) for row in db.execute(text("SELECT id,canonical_name FROM kifu_players ORDER BY id")).mappings()]
        return {"albums": [dict(album)], "slots": snapshot["slots"] if album["black_player_id"] is None else [],
                "catalog": {"players": players}}

    monkeypatch.setattr(batch.first, "_snapshot", live_snapshot)
    assert batch.run(engine, "test", plan)["committed"] is False
    with engine.connect() as db:
        assert db.scalar(text("SELECT black_player_id FROM kifu_albums")) is None
        assert db.scalar(text("SELECT count(*) FROM kifu_players")) == 1
    assert batch.run(engine, "test", plan, apply=True, plan_sha256="reviewed",
                     approved_plan_sha256="reviewed")["committed"] is True
    with engine.connect() as db:
        assert db.scalar(text("SELECT black_player_id FROM kifu_albums")) is not None
        assert db.scalar(text("SELECT count(*) FROM kifu_players")) == 17
