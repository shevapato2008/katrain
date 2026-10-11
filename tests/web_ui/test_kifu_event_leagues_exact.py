import copy
import hashlib
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from katrain.web.kifu import event_leagues_exact as leagues
from katrain.web.core.models_db import KifuSource


# Fields in the immutable 2026-10-04 album preimage, excluding the separately hashed SGF.
HISTORICAL_ALBUM_COLUMNS = (
    "black_player_id", "black_rank", "board_size", "created_at", "date_played", "date_sort",
    "duplicate_of_id", "event", "event_edition_id", "event_id", "handicap", "id", "komi",
    "move_count", "place", "player_black", "player_white", "result", "round_name", "rules",
    "search_text", "source", "source_path", "white_player_id", "white_rank",
)


def test_pinned_partition_and_frozen_identity(monkeypatch):
    monkeypatch.setattr(leagues, "ALBUM_COLUMNS", HISTORICAL_ALBUM_COLUMNS)
    decision, frozen, slots = leagues.evidence("prod")
    assert len(decision["approved_ids"]) == 6810
    assert len(decision["held_ids"]) == 1784
    assert len(slots) == 48
    first = frozen["albums"][0]
    snapshot = {"albums": [{**{key: first[key] for key in leagues.ALBUM_COLUMNS},
                            "sgf_sha256": hashlib.sha256(first["sgf_content"].encode()).hexdigest()}]}
    tiny = {"albums": [first], "album_sources": [], "sources": []}
    snapshot.update(album_sources=[], sources=[])
    leagues._frozen_identity(snapshot, tiny, {}, "test")
    changed = copy.deepcopy(snapshot)
    changed["albums"][0]["source_path"] = "wrong.sgf"
    with pytest.raises(ValueError, match="source_path"):
        leagues._frozen_identity(changed, tiny, {}, "test")


def test_prod_capture_accepts_frozen_catalog_including_event_75(monkeypatch):
    monkeypatch.setattr(leagues, "ALBUM_COLUMNS", HISTORICAL_ALBUM_COLUMNS)
    decision, frozen, slots = leagues.evidence("prod")
    snapshot = {key: copy.deepcopy(frozen[key]) for key in leagues.ANCILLARY}
    snapshot["albums"] = []
    for original in frozen["albums"]:
        row = {key: original[key] for key in leagues.ALBUM_COLUMNS}
        row["sgf_sha256"] = hashlib.sha256(original["sgf_content"].encode()).hexdigest()
        for key in ("black_player_id", "white_player_id"):
            if (row["id"], key) in slots:
                row[key] = slots[(row["id"], key)][1]
        snapshot["albums"].append(row)
    assert sum(old != new for old, new in slots.values()) == 47
    assert sum(old == new for old, new in slots.values()) == 1
    assert any(row["id"] == 75 for row in snapshot["catalog"])
    monkeypatch.setattr(leagues, "_snapshot", lambda db, ids: snapshot)
    db = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    plan = leagues._capture(db, "prod", decision, frozen, slots)
    assert plan["counts"] == {"approved": 6810, "held": 1784}
    snapshot["catalog"] = [row for row in snapshot["catalog"] if row["id"] != 75]
    with pytest.raises(ValueError, match="target differs|catalog differs"):
        leagues._capture(db, "prod", decision, frozen, slots)
    snapshot["catalog"] = copy.deepcopy(frozen["catalog"])
    unreviewed = next(row for row in snapshot["albums"] if (row["id"], "black_player_id") not in slots)
    unreviewed["black_player_id"] = 999999
    with pytest.raises(ValueError, match="unreviewed player FK drift"):
        leagues._capture(db, "prod", decision, frozen, slots)


def test_current_album_schema_rejects_historical_snapshot_before_writes(monkeypatch):
    _, frozen, _ = leagues.evidence("prod")
    original = frozen["albums"][0]
    assert set(leagues.ALBUM_COLUMNS) - set(HISTORICAL_ALBUM_COLUMNS) == {"list_hidden_reason"}
    snapshot = {
        "albums": [{**{key: original.get(key) for key in leagues.ALBUM_COLUMNS},
                    "sgf_sha256": hashlib.sha256(original["sgf_content"].encode()).hexdigest()}],
        "album_sources": [], "sources": [],
    }
    monkeypatch.setattr(leagues, "_snapshot", lambda *args: snapshot)
    db = SimpleNamespace(
        bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
        execute=lambda *args: pytest.fail("schema drift must reject before writes"),
    )
    decision = {"approved_ids": [original["id"]], "held_ids": []}
    with pytest.raises(KeyError, match="list_hidden_reason"):
        leagues._capture(db, "prod", decision, {"albums": [original]}, {})


def test_snapshot_includes_global_unlinked_source(monkeypatch):
    def rows(db, model, columns=None, criterion=None):
        if model is KifuSource:
            assert criterion is None
            return [{"id": 1, "source_key": "19x19"}, {"id": 2, "source_key": "cwi"}]
        if model is leagues.KifuAlbum:
            return [{"id": 1, "sgf_content": "(;)", "event_id": None}]
        if model is leagues.KifuAlbumSource:
            return [{"id": 1, "album_id": 1, "source_id": 1}]
        return []

    monkeypatch.setattr(leagues, "_rows", rows)
    snapshot = leagues._snapshot(object(), [1])
    assert [row["id"] for row in snapshot["sources"]] == [1, 2]


def test_exact_event_transaction_dry_commit_and_cas(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'leagues.db'}")
    with engine.begin() as db:
        db.execute(text("CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, event_id INTEGER, event_edition_id INTEGER, event TEXT, date_played TEXT)"))
        db.execute(text("INSERT INTO kifu_albums VALUES (1,NULL,NULL,'league raw','2026-01-01')"))
    decision = {"approved": [{"id": 1, "event": "league raw", "date_played": "2026-01-01", "target_event_id": 41}],
                "approved_ids": [1], "held_ids": []}
    plan = {"format": "kifu-event-six-leagues-exact-plan-v1", "environment": "test",
            "database": "katrain_db", "targets": {"41": 101},
            "snapshot": {"albums": [{"id": 1, "event_id": None}]}, "counts": {"approved": 1, "held": 0}}
    monkeypatch.setattr(leagues, "evidence", lambda environment: (decision, {}, {}))
    monkeypatch.setattr(leagues, "_capture", lambda db, *args: plan)

    def snapshot(db, ids):
        return {"albums": [dict(row) for row in db.execute(text("SELECT id,event_id FROM kifu_albums")).mappings()]}
    monkeypatch.setattr(leagues, "_snapshot", snapshot)
    assert leagues.run(engine, "test", plan) == {"committed": False, "approved": 1, "held": 0}
    with engine.connect() as db:
        assert db.scalar(text("SELECT event_id FROM kifu_albums WHERE id=1")) is None
    assert leagues.run(engine, "test", plan, apply=True, plan_sha256="reviewed", approved_plan_sha256="reviewed") == {
        "committed": True, "approved": 1, "held": 0}
    with engine.connect() as db:
        assert db.scalar(text("SELECT event_id FROM kifu_albums WHERE id=1")) == 101
    with pytest.raises(ValueError, match="CAS failed"):
        leagues.run(engine, "test", plan)
