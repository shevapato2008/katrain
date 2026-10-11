import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, insert, text
from sqlalchemy.orm import Session


def _module():
    from katrain.web.kifu import event_after_korean_exact

    return event_after_korean_exact


@pytest.fixture
def historical_album_schema(monkeypatch):
    exact = _module()
    columns = exact._pinned(*exact.FROZEN["test"])["album_columns"]
    assert len(columns) == 26
    # These tests inspect the reviewed 2026-10-04 schema, not a current-model replay.
    model = SimpleNamespace(__table__=SimpleNamespace(columns=[SimpleNamespace(name=name) for name in columns]))
    monkeypatch.setattr(exact, "KifuAlbum", model)


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_current_album_schema_rejects_historical_plan_before_database_access(environment):
    exact = _module()
    historical = set(exact._pinned(*exact.FROZEN[environment])["album_columns"])
    current = {column.name for column in exact.KifuAlbum.__table__.columns}
    assert current - historical == {"list_hidden_reason"}
    with pytest.raises(ValueError, match="frozen exact album/statistics/schema scope differs"):
        exact.run(None, environment, {}, apply=True, plan_sha256="reviewed", approved_plan_sha256="reviewed")


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_pinned_exact_scope_and_expanded_guards(environment, monkeypatch, historical_album_schema):
    exact = _module()
    decision, frozen, sha = exact.evidence(environment)
    assert (len(decision["approved"]), len(decision["held"])) == (1209, 476)
    assert len(decision["prior_hold_union_ids"]) == 4292
    assert len(decision["post_review_total_hold_union_ids"]) == 4768
    assert len(frozen["album_columns"]) == 26
    assert {f["family_key"]: f["approved_count"] for f in decision["families"]} == {
        "cn_lanke": 561,
        "kr_kiwang": 353,
        "kr_ten": 295,
    }
    snapshot = {key: copy.deepcopy(frozen[key]) for key in exact.SNAPSHOT_KEYS}
    monkeypatch.setattr(exact, "_snapshot", lambda *args: snapshot)
    db = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    plan = exact._capture(db, decision, frozen, environment, sha)
    assert plan["counts"] == {"approved": 1209, "held": 476, "prior_held": 4292}
    assert plan["source_manifest_sha256"] == exact.SOURCE_SHA
    assert plan["rebase_sha256"] == exact.REBASE_SHA
    assert plan["frozen_file_sha256"] == exact.REBASED[environment][1]
    assert plan["targets"] == exact.FAMILY_NAMES
    for key, field, value in [
        ("albums", "sgf_content", "changed"),
        ("albums", "search_text", "changed"),
        ("albums", "black_player_id", 999999),
        ("album_sources", "origin_path", "wrong.sgf"),
        ("players", "canonical_name", "changed"),
        ("sources", "display_name", "changed"),
        ("events", "canonical_name", "changed"),
        ("aliases", "alias", "changed"),
        ("editions", "edition_label", "changed"),
        ("existing_hold_event_slots", "event_id", 92),
    ]:
        old = snapshot[key][0][field]
        snapshot[key][0][field] = value
        with pytest.raises(ValueError, match="frozen " + key):
            exact._capture(db, decision, frozen, environment, sha)
        snapshot[key][0][field] = old
    committed = next(row for row in snapshot["events"] if row["id"] == 92)
    old = committed["created_at"]
    committed["created_at"] = None
    with pytest.raises(ValueError, match="frozen events"):
        exact._capture(db, decision, frozen, environment, sha)
    committed["created_at"] = old
    snapshot["events"].append({"id": 999999, "canonical_name": "未审核类型", "created_at": None})
    with pytest.raises(ValueError, match="frozen events"):
        exact._capture(db, decision, frozen, environment, sha)
    snapshot["events"].pop()
    snapshot["album_columns"].append("unreviewed_column")
    with pytest.raises(ValueError, match="frozen album_columns"):
        exact._capture(db, decision, frozen, environment, sha)
    snapshot["album_columns"].pop()
    snapshot["statistics"]["event_links"] += 1
    with pytest.raises(ValueError, match="frozen statistics"):
        exact._capture(db, decision, frozen, environment, sha)
    snapshot["statistics"]["event_links"] -= 1
    snapshot["global_counts"]["player_links"] += 1
    with pytest.raises(ValueError, match="frozen global_counts"):
        exact._capture(db, decision, frozen, environment, sha)


def test_source_manifest_tamper_is_rejected(tmp_path, monkeypatch):
    exact = _module()
    for relative in (exact.DECISION_PATH, exact.SOURCE_PATH):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((exact.ROOT / relative).read_bytes())
    with (tmp_path / exact.SOURCE_PATH).open("ab") as stream:
        stream.write(b" ")
    monkeypatch.setattr(exact, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="pinned evidence SHA differs"):
        exact.evidence("test")


@pytest.mark.parametrize("environment,target", [("test", 247), ("prod", 246)])
def test_exact_rebase_preserves_changed_event_hold(environment, target, historical_album_schema):
    exact = _module()
    decision, fresh, _ = exact.evidence(environment)
    held = next(row for row in decision["held"] if row["id"] == 12087)
    album = next(row for row in fresh["albums"] if row["id"] == 12087)
    assert held["environments"][environment.upper()]["white_player_id"] is None
    assert album["white_player_id"] == target
    assert album["event_id"] is None and album["event_edition_id"] is None
    assert fresh["global_counts"]["player_links"] == (310270 if environment == "test" else 311875)
    assert len(fresh["players"]) == (581 if environment == "test" else 582)


@pytest.mark.parametrize("mutation", ["held_fk", "unexpected_column", "added_player", "player_links", "original_row"])
def test_exact_rebase_rejects_unexpected_drift(monkeypatch, mutation, historical_album_schema):
    exact = _module()
    pinned = exact._pinned

    def tampered(path, sha):
        data = pinned(path, sha)
        if (
            path
            == "docs/resource/kifu-event-after-korean-two-next-TEST-post-top20-independent-full-preimage-2026-10-04.json.gz"
        ):
            if mutation in ("held_fk", "unexpected_column"):
                album = next(row for row in data["albums"] if row["id"] == 12087)
                album["white_player_id" if mutation == "held_fk" else "search_text"] = "unapproved"
            elif mutation == "added_player":
                next(row for row in data["players"] if row["id"] == 247)["canonical_name"] = "unapproved"
            elif mutation == "player_links":
                data["global_counts"]["player_links"] += 1
        if path == exact.FROZEN["test"][0] and mutation == "original_row":
            next(row for row in data["albums"] if row["id"] == 12087)["white_player_id"] = 247
        return data

    monkeypatch.setattr(exact, "_pinned", tampered)
    with pytest.raises(ValueError):
        exact.evidence("test")


@pytest.fixture
def local_exact_case(tmp_path, monkeypatch):
    exact = _module()
    from katrain.web.core.models_db import (
        KifuAlbum,
        KifuAlbumSource,
        KifuEvent,
        KifuEventAlias,
        KifuEventEdition,
        KifuPlayer,
        KifuSource,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'exact.db'}")
    models = [KifuPlayer, KifuSource, KifuEvent, KifuEventEdition, KifuEventAlias, KifuAlbum, KifuAlbumSource]
    for model in models:
        model.__table__.create(engine)
    with engine.begin() as db:
        db.execute(insert(KifuPlayer), {"id": 1, "canonical_name": "棋手", "created_at": None})
        db.execute(insert(KifuSource), {"id": 1, "source_key": "19x19", "created_at": None})
        db.execute(insert(KifuEvent), {"id": 90, "canonical_name": "已有类型", "created_at": None})
        db.execute(
            insert(KifuEventAlias),
            {"id": 1, "event_id": 90, "alias": "旧名称", "normalized_alias": "旧名称", "created_at": None},
        )
        db.execute(
            insert(KifuEventEdition),
            {"id": 1, "event_id": 90, "edition_label": "旧届次", "created_at": None},
        )
        for id_ in range(1, 6):
            db.execute(
                insert(KifuAlbum),
                {
                    "id": id_,
                    "player_black": "棋手",
                    "player_white": "棋手",
                    "black_player_id": 1,
                    "white_player_id": 1,
                    "event": f"原赛事 {id_}",
                    "date_played": "2020-01-01",
                    "sgf_content": f"original-sgf-{id_}",
                    "source_path": f"fixture/{id_}.sgf",
                    "search_text": f"original-search-{id_}",
                    "created_at": None,
                },
            )
            db.execute(
                insert(KifuAlbumSource),
                {
                    "id": id_,
                    "album_id": id_,
                    "source_id": 1,
                    "origin_path": f"fixture/{id_}.sgf",
                    "match_method": "source_path",
                    "created_at": None,
                },
            )
    decision = {
        "approved": [
            {
                "id": id_,
                "family_key": family,
                "raw_preimage": {"event": f"原赛事 {id_}", "date_played": "2020-01-01"},
            }
            for id_, family in enumerate(exact.FAMILY_NAMES, 1)
        ],
        "approved_ids": [1, 2, 3],
        "held_ids": [4],
        "prior_hold_union_ids": [5],
    }
    with Session(engine) as db:
        frozen = exact._snapshot(db, [1, 2, 3, 4], [1], [5])
    monkeypatch.setattr(exact, "evidence", lambda environment: (decision, frozen, exact.DECISION_SHA))
    plan = exact.capture(engine, "test")
    yield exact, engine, decision, frozen, plan
    engine.dispose()


def test_real_capture_dry_rollback_and_only_approved_event_updates(local_exact_case):
    exact, engine, decision, initial, plan = local_exact_case
    with pytest.raises(ValueError, match="approved plan SHA"):
        exact.run(engine, "test", plan, apply=True)
    assert exact.run(engine, "test", plan)["committed"] is False
    with Session(engine) as db:
        assert exact._snapshot(db, [1, 2, 3, 4], [1], [5]) == initial
    result = exact.run(engine, "test", plan, apply=True, plan_sha256="approved", approved_plan_sha256="approved")
    assert result["committed"] is True
    with Session(engine) as db:
        current = exact._snapshot(db, [1, 2, 3, 4], [1], [5])
    expected = copy.deepcopy(initial)
    for row in decision["approved"]:
        expected["albums"][row["id"] - 1]["event_id"] = result["created_event_ids"][row["family_key"]]
    expected["events"] += [row for row in current["events"] if row["id"] != 90]
    expected["statistics"]["event_links"] += 3
    expected["global_counts"]["event_links"] += 3
    assert current == expected
    with pytest.raises(ValueError, match="frozen albums"):
        exact.run(engine, "test", plan)
    with Session(engine) as db:
        assert exact._snapshot(db, [1, 2, 3, 4], [1], [5]) == current


def test_unexpected_held_row_mutation_rolls_back_entire_transaction(local_exact_case):
    exact, engine, _, initial, plan = local_exact_case
    with engine.begin() as db:
        db.execute(
            text(
                "CREATE TRIGGER unexpected_write AFTER UPDATE OF event_id ON kifu_albums "
                "WHEN NEW.id=1 BEGIN UPDATE kifu_albums SET result='unexpected' WHERE id=4; END"
            )
        )
    with pytest.raises(ValueError, match="in-transaction full postimage"):
        exact.run(engine, "test", plan, apply=True, plan_sha256="approved", approved_plan_sha256="approved")
    with Session(engine) as db:
        assert exact._snapshot(db, [1, 2, 3, 4], [1], [5]) == initial


def test_cli_rejects_plan_byte_mismatch_before_run(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[2] / "scripts/kifu_event_after_korean_exact.py"
    assert script.is_file(), "exact-only CLI is required"
    spec = importlib.util.spec_from_file_location("after_korean_exact_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"unexpected": "plan"}))
    monkeypatch.setattr(module, "run", lambda *args, **kwargs: pytest.fail("run must not receive altered plan bytes"))
    with pytest.raises(ValueError, match="plan file byte SHA differs"):
        module.main(
            [
                "dry",
                "--environment",
                "test",
                "--plan",
                str(plan),
                "--plan-sha256",
                "wrong",
                "--database-url",
                "sqlite://",
            ]
        )
