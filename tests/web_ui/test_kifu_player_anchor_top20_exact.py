import copy
import importlib
import json
import sqlite3

import pytest
from sqlalchemy import create_engine, text


def executor():
    return importlib.import_module("katrain.web.kifu.player_anchor_top20_exact")


@pytest.fixture(scope="module")
def frozen_test():
    return executor().evidence("test")


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_frozen_evidence_and_only_enumerated_rebase(environment):
    exact = executor()
    decision, expected = exact.evidence(environment)
    assert (len(decision["approved"]), len(decision["held"])) == (1933, 1415)
    assert len(expected["albums"]) == 3316
    assert len(expected["existing_owner_context"]["albums"]) == 5583
    assert len(expected["slots"]) == 3348
    assert next(row for row in expected["albums"] if row["id"] == 70944)["event_id"] == 92


@pytest.mark.parametrize(
    "section",
    [
        "albums",
        "album_sources",
        "catalog",
        "raw_staging",
        "event_aliases",
        "existing_owner_context",
        "global_counts",
        "slots",
    ],
)
def test_complete_snapshot_rejects_drift(section, frozen_test):
    exact = executor()
    _, expected = frozen_test
    actual = copy.deepcopy(expected)
    if section == "catalog":
        actual[section]["names"][0]["revision"] += 1
    elif section == "existing_owner_context":
        actual[section]["albums"][-1]["sgf_content"] += "changed"
    elif section == "global_counts":
        actual[section]["player_links"] += 1
    elif section == "albums":
        actual[section][0]["sgf_content"] += "changed"
    else:
        actual[section].pop()
    with pytest.raises(ValueError, match="preimage differs"):
        exact._validate_snapshot(actual, expected)


def test_postimage_changes_exact_fks_and_held_opponent_only(frozen_test):
    exact = executor()
    decision, expected = frozen_test
    after = exact._after(expected, decision["approved"], "test")
    wanted = {
        (row["album_id"], row["side"]): row["target_player_id_by_environment"]["TEST"] for row in decision["approved"]
    }
    changes = {}
    for before, current in zip(expected["albums"], after["albums"]):
        for key in before:
            if before[key] != current[key]:
                assert key in ("black_player_id", "white_player_id")
                changes[(before["id"], key.split("_")[0])] = current[key]
    assert changes == wanted
    assert len(after["slots"]) == 1415
    assert after["global_counts"]["player_links"] == expected["global_counts"]["player_links"] + 1933
    for row in decision["held"]:
        album = next(a for a in after["albums"] if a["id"] == row["album_id"])
        assert album[row["side"] + "_player_id"] is None


def test_apply_requires_separate_exact_plan_approval():
    exact = executor()
    with pytest.raises(ValueError, match="approved plan SHA"):
        exact.run(None, "test", {}, apply=True, plan_sha256="one", approved_plan_sha256="two")


def test_postcommit_verification_failure_reports_successful_commit(tmp_path, monkeypatch):
    exact = executor()
    engine = create_engine(f"sqlite:///{tmp_path / 'postcommit.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, player_black TEXT, "
                "date_played TEXT, black_player_id INTEGER)"
            )
        )
        conn.execute(text("INSERT INTO kifu_albums VALUES (1,'target','2020-01-01',NULL)"))
    album = {
        "id": 1,
        "player_black": "target",
        "player_white": "other",
        "date_played": "2020-01-01",
        "black_player_id": None,
        "white_player_id": None,
    }
    snapshot = {key: [] for key in exact.GUARDS}
    snapshot.update(
        albums=[album],
        existing_owner_context={"albums": [album]},
        variant_scan_inputs={"target": ["target"]},
        global_counts={"player_links": 0},
    )
    snapshot["slots"] = exact._slots([album], ["target"])
    decision = {
        "scope": {"raws": ["target"]},
        "approved": [{"album_id": 1, "side": "black", "raw": "target", "target_player_id_by_environment": {"TEST": 7}}],
    }
    counts = {"approved": 1, "held": 0}
    monkeypatch.setattr(exact, "COUNTS", counts)
    monkeypatch.setattr(exact, "evidence", lambda environment: (decision, snapshot))
    calls = 0
    failure = ValueError("independent postimage differs")

    def read(db, current_decision, expected):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise failure
        return copy.deepcopy(snapshot) if calls == 1 else exact._after(snapshot, decision["approved"], "test")

    monkeypatch.setattr(exact, "_snapshot", read)
    plan = {
        "format": exact.FORMAT,
        "environment": "test",
        "database": exact.DATABASES["test"],
        "decision_sha256": exact.DECISION_SHA,
        "rebase_sha256": exact.REBASE_SHA,
        "source_manifest_sha256": exact.SOURCE_SHA,
        "snapshot": snapshot,
        "counts": counts,
    }
    with pytest.raises(RuntimeError, match="commit succeeded; independent postcommit verification failed") as caught:
        exact.run(engine, "test", plan, apply=True, plan_sha256="approved", approved_plan_sha256="approved")
    assert caught.value.__cause__ is failure
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT black_player_id FROM kifu_albums WHERE id=1")) == 7
    engine.dispose()


def test_isolated_full_frozen_capture_dry_apply(tmp_path, frozen_test):
    """Replay all guarded rows; synthetic out-of-scope rows supply global counts."""
    exact = executor()
    _, expected = frozen_test
    sqlite3.register_converter("TOP20_JSON", json.loads)
    path = tmp_path / "top20.db"
    db = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
    tables = {exact.TABLES[key]: expected[key] for key in ("sources", "events", "event_editions", "event_aliases")}
    tables.update({exact.TABLES[key]: expected["catalog"][key] for key in ("players", "aliases", "names")})
    tables.update(
        {
            "kifu_albums": expected["existing_owner_context"]["albums"],
            "kifu_album_sources": expected["existing_owner_context"]["album_sources"],
            "kifu_raw_player_values": expected["raw_staging"],
        }
    )
    for table, rows in tables.items():
        keys = list(rows[0])
        columns = []
        for key in keys:
            value = next((row[key] for row in rows if row[key] is not None), None)
            kind = (
                "TOP20_JSON"
                if isinstance(value, (dict, list))
                else "INTEGER" if isinstance(value, int) else "REAL" if isinstance(value, float) else "TEXT"
            )
            columns.append('"' + key + '" ' + kind + (" PRIMARY KEY" if key == "id" else ""))
        db.execute("CREATE TABLE " + table + " (" + ",".join(columns) + ")")
        db.executemany(
            "INSERT INTO " + table + " VALUES (" + ",".join("?" for _ in keys) + ")",
            [
                [
                    json.dumps(row[key], ensure_ascii=False) if isinstance(row[key], (dict, list)) else row[key]
                    for key in keys
                ]
                for row in rows
            ],
        )
    albums = tables["kifu_albums"]
    counts = expected["global_counts"]
    games = counts["games"] - len(albums)
    links = counts["player_links"] - sum(
        row[side + "_player_id"] is not None for row in albums for side in ("black", "white")
    )
    events = counts["event_links"] - sum(row["event_id"] is not None for row in albums)
    db.executemany(
        "INSERT INTO kifu_albums (id,player_black,player_white,black_player_id,white_player_id,event_id) VALUES (?,?,?,?,?,?)",
        [
            (
                500000 + i,
                "isolated counter",
                "isolated counter",
                999999 if 2 * i < links else None,
                999999 if 2 * i + 1 < links else None,
                1 if i < events else None,
            )
            for i in range(games)
        ],
    )
    db.commit()
    db.close()
    # A SQLite fixture converter preserves the frozen JSON dictionaries for the
    # executor's raw SQL reads, as PostgreSQL's JSON driver does in deployment.
    engine = create_engine(f"sqlite:///{path}", connect_args={"detect_types": sqlite3.PARSE_DECLTYPES})
    plan = exact.capture(engine, "test")
    assert exact.run(engine, "test", plan)["committed"] is False
    result = exact.run(
        engine, "test", plan, apply=True, plan_sha256="local-reviewed", approved_plan_sha256="local-reviewed"
    )
    assert result == {"committed": True, "created_player_ids": {}, "approved": 1933, "held": 1415}
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(black_player_id)+count(white_player_id) FROM kifu_albums")) == 310270
        held = exact.base._pin(exact.DECISION_PATH, exact.DECISION_SHA)["held"][0]
        assert (
            conn.scalar(
                text(f"SELECT {held['side']}_player_id FROM kifu_albums WHERE id=:id"), {"id": held["album_id"]}
            )
            is None
        )
        assert conn.scalar(text("SELECT count(*) FROM kifu_players")) == len(expected["catalog"]["players"])
    with pytest.raises(ValueError, match="preimage differs"):
        exact.capture(engine, "test")
    engine.dispose()
