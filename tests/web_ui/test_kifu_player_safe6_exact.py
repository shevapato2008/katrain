import copy
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from katrain.web.core.models_db import KifuPlayer
from katrain.web.kifu import player_safe6_exact as safe6


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_ahan_exact_rebase_rejects_unreviewed_overlap_drift(environment):
    decision = safe6.base._pin(safe6.DECISION_PATH, safe6.DECISION_SHA)
    baseline = copy.deepcopy(decision["environment_preimages"][environment]["snapshot"])
    rebased = safe6._ahan_rebase(decision, baseline, environment)
    assert len(rebased["events"]) == 80
    assert {row["id"] for row in rebased["albums"] if row["event_id"] == 89} == safe6.AHAN_OVERLAP
    next(row for row in baseline["albums"] if row["id"] == 103194)["black_player_id"] = 999999
    with pytest.raises(ValueError, match="full album postimage"):
        safe6._ahan_rebase(decision, baseline, environment)


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_pinned_decision_and_full_capture_guards(environment, monkeypatch):
    decision, expected = safe6.evidence(environment)
    assert len(decision["approved_slots"]) == 601
    assert len(decision["held_slots"]) == 180
    snapshot = copy.deepcopy(expected)
    monkeypatch.setattr(safe6.base, "_snapshot", lambda *args: snapshot)
    db = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    plan = safe6._capture(db, environment, decision, expected)
    assert plan["counts"] == {"approved": 601, "held": 180}
    held = decision["held_slots"][0]
    album = next(row for row in snapshot["albums"] if row["id"] == held["album_id"])
    album[held["side"] + "_player_id"] = 999999
    with pytest.raises(ValueError, match="albums preimage"):
        safe6._capture(db, environment, decision, expected)
    album[held["side"] + "_player_id"] = None
    snapshot["catalog"]["names"][0]["revision"] = 999
    with pytest.raises(ValueError, match="names catalog preimage"):
        safe6._capture(db, environment, decision, expected)


def test_semantic_timestamp_only():
    a = {"created_at": "2026-09-30T19:51:48.80822+00:00", "verified_at": "2026-10-03T13:57:25.73626+00:00", "value": "same"}
    b = {"created_at": "2026-09-30T19:51:48.808220+00:00", "verified_at": "2026-10-03T13:57:25.736260+00:00", "value": "same"}
    assert safe6._equal(a, b)
    b["verified_at"] = "2026-10-03T13:57:25.736261+00:00"
    assert not safe6._equal(a, b)
    b["verified_at"] = a["verified_at"]
    b["value"] = "changed"
    assert not safe6._equal(a, b)


def test_real_snapshot_helper_receives_complete_frozen_shape(monkeypatch):
    decision, expected = safe6.evidence("test")
    tables = {
        safe6.base.KifuAlbum: expected["albums"],
        safe6.base.KifuAlbumSource: expected["album_sources"],
        safe6.base.KifuRawPlayerValue: expected["raw_staging"],
        safe6.base.KifuSource: expected["sources"],
        safe6.base.KifuEvent: expected["events"],
        safe6.base.KifuEventEdition: expected["event_editions"],
        safe6.base.KifuPlayer: expected["catalog"]["players"],
        safe6.base.KifuPlayerAlias: expected["catalog"]["aliases"],
        safe6.base.KifuPlayerName: expected["catalog"]["names"],
    }
    touched = []

    def rows(db, model, keys, criterion=None):
        touched.append(model)
        assert set(keys) == set(tables[model][0])
        return copy.deepcopy(tables[model])

    monkeypatch.setattr(safe6.base, "_rows", rows)
    db = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
                         scalars=lambda query: [SimpleNamespace(**row) for row in expected["albums"]])
    plan = safe6._capture(db, "test", decision, expected)
    assert plan["counts"] == {"approved": 601, "held": 180}
    assert set(touched) == set(tables)


def test_transaction_rollback_commit_and_cas(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'safe6.db'}")
    KifuPlayer.__table__.create(engine)
    with engine.begin() as db:
        db.execute(text("CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, player_black TEXT, player_white TEXT, date_played TEXT, black_player_id INTEGER, white_player_id INTEGER)"))
        db.execute(text("INSERT INTO kifu_albums VALUES (1,'赵哲伦','X','2020-01-01',NULL,NULL)"))
        db.execute(text("INSERT INTO kifu_albums VALUES (2,'陈嘉锐','X','2020-01-01',NULL,NULL)"))
        db.execute(text("INSERT INTO kifu_albums VALUES (3,'HOLD','X','2020-01-01',NULL,NULL)"))
    decision = {"scope": {"raws": ["赵哲伦", "陈嘉锐"]},
                "identities": [{"raw": "赵哲伦", "chinese_canonical": "赵哲伦", "target_ids": {"test": None}},
                               {"raw": "陈嘉锐", "chinese_canonical": "陈嘉锐", "target_ids": {"test": None}}],
                "approved_slots": [{"album_id": 1, "side": "black", "raw": "赵哲伦", "date_played": "2020-01-01"},
                                   {"album_id": 2, "side": "black", "raw": "陈嘉锐", "date_played": "2020-01-01"}]}
    plan = {"format": safe6.FORMAT, "environment": "test", "database": "katrain_db",
            "decision_sha256": safe6.DECISION_SHA,
            "snapshot": {"albums": [{"id": 1, "black_player_id": None}, {"id": 2, "black_player_id": None},
                                    {"id": 3, "black_player_id": None}], "slots": [],
                         "catalog": {"players": []}}, "counts": {"approved": 2, "held": 1}}
    monkeypatch.setattr(safe6, "evidence", lambda env: (decision, {"albums": [], "album_sources": [], "raw_staging": []}))
    monkeypatch.setattr(safe6, "_capture", lambda *args: plan)

    def snapshot(db, *args):
        return {"albums": [dict(row) for row in db.execute(text("SELECT id,black_player_id FROM kifu_albums ORDER BY id")).mappings()],
                "slots": [], "catalog": {"players": [dict(row) for row in db.execute(text("SELECT id,canonical_name,created_at FROM kifu_players ORDER BY id")).mappings()]}}
    monkeypatch.setattr(safe6.base, "_snapshot", snapshot)
    assert safe6.run(engine, "test", plan)["committed"] is False
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM kifu_players")) == 0
    result = safe6.run(engine, "test", plan, apply=True, plan_sha256="yes", approved_plan_sha256="yes")
    assert result["committed"] is True
    with engine.connect() as db:
        assert db.scalar(text("SELECT black_player_id FROM kifu_albums WHERE id=3")) is None
    with pytest.raises(ValueError, match="CAS failed"):
        safe6.run(engine, "test", plan)
