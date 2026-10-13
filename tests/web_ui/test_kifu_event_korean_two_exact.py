import copy
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text


def _module():
    from katrain.web.kifu import event_korean_two_exact

    return event_korean_two_exact


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_frozen_scope_rebase_and_protected_capture(environment, monkeypatch):
    korean = _module()
    decision, frozen, sha = korean.evidence(environment)
    assert (len(decision["approved"]), len(decision["held"])) == (737, 19)
    assert len(decision["prior_hold_union_ids"]) == 4273
    snapshot = {key: copy.deepcopy(frozen[key]) for key in korean.SNAPSHOT_KEYS}
    monkeypatch.setattr(korean, "_snapshot", lambda *args: snapshot)
    db = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    plan = korean._capture(db, decision, frozen, environment, sha)
    assert plan["counts"] == {"approved": 737, "held": 19, "prior_held": 4273}
    assert plan["targets"] == korean.FAMILY_NAMES
    for key, field, value in [
        ("albums", "black_player_id", 999999),
        ("album_sources", "origin_path", "wrong.sgf"),
        ("players", "canonical_name", "changed"),
        ("sources", "display_name", "changed"),
        ("events", "canonical_name", "changed"),
        ("aliases", "alias", "changed"),
        ("editions", "edition_label", "changed"),
        ("existing_hold_event_slots", "event_id", 89),
    ]:
        old = snapshot[key][0][field]
        snapshot[key][0][field] = value
        with pytest.raises(ValueError, match="frozen " + key):
            korean._capture(db, decision, frozen, environment, sha)
        snapshot[key][0][field] = old
    snapshot["statistics"]["event_links"] += 1
    with pytest.raises(ValueError, match="statistics"):
        korean._capture(db, decision, frozen, environment, sha)


def test_dry_apply_only_event_cells_cas_and_independent_verification(monkeypatch, tmp_path):
    korean = _module()
    engine = create_engine(f"sqlite:///{tmp_path / 'korean.db'}")
    with engine.begin() as db:
        db.execute(
            text(
                "CREATE TABLE kifu_events (id INTEGER PRIMARY KEY, canonical_name TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        db.execute(
            text(
                "CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, event TEXT, date_played TEXT, event_id INTEGER, event_edition_id INTEGER)"
            )
        )
        for id_, raw in [(1, "gs"), (2, "women"), (3, "hold")]:
            db.execute(
                text("INSERT INTO kifu_albums VALUES (:id,:raw,'2020-01-01',NULL,NULL)"), {"id": id_, "raw": raw}
            )
    decision = {
        "approved": [
            {"id": id_, "family_key": family, "raw_preimage": {"event": raw, "date_played": "2020-01-01"}}
            for id_, family, raw in [(1, "kr_gs_caltex", "gs"), (2, "kr_womens_guksu", "women")]
        ],
        "approved_ids": [1, 2],
        "held_ids": [3],
        "prior_hold_union_ids": [],
    }

    def snapshot(db, *args):
        return {
            "albums": [
                dict(r)
                for r in db.execute(text("SELECT id,event_id,event_edition_id FROM kifu_albums ORDER BY id")).mappings()
            ],
            "events": [
                dict(r)
                for r in db.execute(text("SELECT id,canonical_name,created_at FROM kifu_events ORDER BY id")).mappings()
            ],
            "players": [],
            "statistics": {
                "albums": 3,
                "event_links": db.scalar(text("SELECT count(event_id) FROM kifu_albums")),
                "edition_links": 0,
            },
        }

    monkeypatch.setattr(korean, "_snapshot", snapshot)
    with engine.connect() as db:
        initial = snapshot(db)
    plan = {
        "format": "kifu-event-korean-two-exact-plan-v1",
        "environment": "test",
        "database": "katrain_db",
        "targets": korean.FAMILY_NAMES,
        "snapshot": initial,
        "counts": {"approved": 2, "held": 1, "prior_held": 0},
    }
    monkeypatch.setattr(korean, "evidence", lambda env: (decision, {}, "sha"))
    monkeypatch.setattr(korean, "_capture", lambda *args: plan)
    with pytest.raises(ValueError, match="approved plan SHA"):
        korean.run(engine, "test", plan, apply=True)
    assert korean.run(engine, "test", plan)["committed"] is False
    with engine.connect() as db:
        assert snapshot(db) == initial
    result = korean.run(engine, "test", plan, apply=True, plan_sha256="approved", approved_plan_sha256="approved")
    assert result["committed"] is True
    with engine.connect() as db:
        current = snapshot(db)
    assert [r["canonical_name"] for r in current["events"]] == list(korean.FAMILY_NAMES.values())
    assert current["albums"][2] == initial["albums"][2]
    targets = result["created_event_ids"]
    with engine.begin() as db:
        db.execute(text("UPDATE kifu_events SET created_at='changed' WHERE id=1"))
    with pytest.raises(ValueError, match="posttransaction full scope"):
        korean._verify_final(engine, decision, plan, targets, current["events"], True)
    with pytest.raises(ValueError, match="CAS failed"):
        korean.run(engine, "test", plan)


def test_post_ahan_rebase_rejects_unreviewed_catalog_and_player_drift():
    korean = _module()
    _, frozen, _ = korean.evidence("test")
    rebase = korean._pinned(korean.REBASE_PATH, korean.REBASE_SHA)["environments"]["TEST"]
    changed = copy.deepcopy(frozen)
    changed["events"][-1]["canonical_name"] = "unreviewed"
    with pytest.raises(ValueError, match="catalog rebase"):
        korean._validate_ahan_rebase("test", changed, rebase)
    changed = copy.deepcopy(frozen)
    changed["players"][0]["canonical_name"] = "unreviewed"
    with pytest.raises(ValueError, match="unrelated players"):
        korean._validate_ahan_rebase("test", changed, rebase)


def test_name_collision_aborts_even_with_matching_frozen_catalog(monkeypatch):
    korean = _module()
    decision, frozen, sha = korean.evidence("test")
    frozen = copy.deepcopy(frozen)
    frozen["aliases"][0]["normalized_alias"] = "韩国GS加德士杯"
    snapshot = {key: copy.deepcopy(frozen[key]) for key in korean.SNAPSHOT_KEYS}
    monkeypatch.setattr(korean, "_snapshot", lambda *args: snapshot)
    db = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    with pytest.raises(ValueError, match="collides"):
        korean._capture(db, decision, frozen, "test", sha)
