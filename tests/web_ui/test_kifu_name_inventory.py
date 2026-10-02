"""Read-only, reproducible inventory of raw kifu name inputs."""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from katrain.web.core.db import Base
from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumEventSelection, KifuAlbumSource, KifuEventSelectionBatch, KifuSource,
)
from katrain.web.kifu.name_inventory import _script_type, build_inventory
from tests.web_ui._kifu_selection_helpers import apply_reviewed_selection
from scripts.kifu_name_inventory import main


def _engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'albums.db'}")
    Base.metadata.create_all(engine)
    return engine


def _album(number, *, duplicate_of_id=None, **fields):
    values = dict(
        id=number,
        player_black="甲某",
        player_white="乙某",
        event="棋赛",
        sgf_content="(;FF[4])",
        source_path=f"/missing/{number}.sgf",
        source="raw SGF SO",
        date_played="1934-05-01",
        duplicate_of_id=duplicate_of_id,
    )
    values.update(fields)
    return KifuAlbum(**values)


def test_inventory_counts_all_visible_sample_and_detail_populations(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as db:
        db.add_all(
            [
                _album(19, player_black="甲某", player_white="甲某", black_player_id=3, event_id=9),
                _album(20, duplicate_of_id=19, player_black="甲某", player_white="丙某", black_rank="九段"),
                _album(40, player_black="甲某]BR[九段", player_white="乙某", white_rank="白九目半胜", event="Engine3.8"),
            ]
        )
        db.add(KifuSource(id=1, source_key="archive", display_name="Archive"))
        db.add(KifuAlbumSource(album_id=20, source_id=1, origin_path="missing-file.sgf", match_method="exact"))
        db.commit()

    result = build_inventory(engine, batch_size=1)
    assert result["counts"] == {"all": 3, "visible": 2, "sample": 2}
    assert result["detail_ids"] == [19, 20, 40]
    assert result["scopes"]["sample"]["album_ids"] == [20, 40]
    assert result["scopes"]["visible"]["album_ids"] == [19, 40]
    player = {item["value"]: item for item in result["scopes"]["all"]["values"]["player"]}
    assert player["甲某"]["occurrences"] == 3
    assert player["甲某"]["affected_games"] == 2
    assert result["scopes"]["all"]["identity_ids"]["black_player_id"] == {"3": 1, "null": 2}
    assert result["scopes"]["all"]["identity_ids"]["event_id"] == {"9": 1, "null": 2}
    assert result["scopes"]["all"]["values"]["black_rank"] == [
        {"value": None, "occurrences": 2, "affected_games": 2},
        {"value": "九段", "occurrences": 1, "affected_games": 1},
    ]
    assert result["source_stats"]["all"]["archive"] == {"links": 1, "affected_games": 1}
    assert result["source_stats"]["visible"] == {}
    assert result["unlinked_source_counts"] == {"all": 2, "visible": 2, "sample": 1}
    assert result["sgf_source_stats"]["all"] == [{"value": "raw SGF SO", "occurrences": 3}]
    assert result["script_stats"]["all"]["player_black"]["mixed"] == 1
    assert result["era_stats"]["all"]["1930s"] == 3
    assert len(result["sha256"]) == 64
    assert result["distinct_values"]["all"]["player"] == 4


def test_inventory_hash_is_stable_and_sensitive_to_null_unicode_and_provenance(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as db:
        db.add_all([_album(40, event=None), _album(20, event="", player_black="棋士")])
        db.add(KifuSource(id=1, source_key="collection"))
        db.add(KifuAlbumSource(album_id=20, source_id=1, origin_path="a.sgf", match_method="import"))
        db.commit()
    first = build_inventory(engine, batch_size=1)
    assert build_inventory(engine, batch_size=99)["sha256"] == first["sha256"]
    assert first["sha256"] != hashlib.sha256(b"").hexdigest()
    assert {item["value"] for item in first["scopes"]["all"]["values"]["event"]} == {None, ""}
    with Session(engine) as db:
        db.get(KifuAlbum, 40).event = ""
        db.commit()
    assert build_inventory(engine)["sha256"] != first["sha256"]
    before_provenance_change = build_inventory(engine)["sha256"]
    with Session(engine) as db:
        db.query(KifuAlbumSource).one().origin_path = "b.sgf"
        db.commit()
    assert build_inventory(engine)["sha256"] != before_provenance_change


def test_reviewed_second_gn_adds_hashed_selection_supplement_without_changing_legacy_album(tmp_path):
    engine = _engine(tmp_path)
    sgf = ("(;FF[4]SZ[19]SO[https://19x19.com]GN[GNUGo3.8]GN[Selected Cup]"
           "GC[Selected Cup | 194 moves])")
    with Session(engine) as db:
        db.add(_album(20, event="GNUGo3.8", sgf_content=sgf, source="https://19x19.com",
                      source_path="data/kifu-album/19x19/a.sgf"))
        db.commit()
    original = build_inventory(engine)
    assert original["inventory_format"] == 2
    assert "event_selection" not in original
    apply_reviewed_selection(engine, 20)
    selected = build_inventory(engine)
    assert selected["inventory_format"] == 3
    assert selected["sha256"] != original["sha256"]
    assert selected["album_associations"] == original["album_associations"]
    assert selected["event_selection"]["rows"][0][0:3] == [20, "Selected Cup", hashlib.sha256(sgf.encode()).hexdigest()]
    assert build_inventory(engine, batch_size=1)["sha256"] == selected["sha256"]
    with Session(engine) as db:
        db.get(KifuAlbumEventSelection, 20).selected_raw = "Other Cup"
        db.commit()
    assert build_inventory(engine)["event_selection"]["rows"] == []
    with Session(engine) as db:
        db.get(KifuAlbumEventSelection, 20).selected_raw = "Selected Cup"
        db.commit()
    with Session(engine) as db:
        db.get(KifuAlbum, 20).sgf_content += "\n"
        db.commit()
    drifted = build_inventory(engine)
    assert drifted["event_selection"]["rows"] == []
    assert drifted["sha256"] != selected["sha256"]


def test_inventory_rejects_fabricated_applied_batch_without_review_artifact(tmp_path):
    engine = _engine(tmp_path)
    sgf = ("(;FF[4]SZ[19]SO[https://19x19.com]GN[GNUGo3.8]GN[Selected Cup]"
           "GC[Selected Cup | 194 moves])")
    reviewed_at = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)
    with Session(engine) as db:
        db.add(_album(20, event="GNUGo3.8", sgf_content=sgf,
                      source_path="data/kifu-album/19x19/a.sgf"))
        db.add(KifuEventSelectionBatch(
            id=3, bundle_sha256="a" * 64, member_set_sha256="b" * 64,
            reviewed_artifact={}, producer_id="producer", reviewer_id="reviewer",
            reviewed_at=reviewed_at, status="applied"))
        db.add(KifuAlbumEventSelection(
            album_id=20, batch_id=3, selected_raw="Selected Cup",
            sgf_sha256=hashlib.sha256(sgf.encode()).hexdigest(), property_name="GN", property_index=1,
            status="approved", rule_version="19x19-gnugo-second-gn-v1",
            reviewer_id="reviewer", reviewed_at=reviewed_at))
        db.commit()
    result = build_inventory(engine)
    assert result["inventory_format"] == 3
    assert result["event_selection"]["rows"] == []


def test_album_associations_expose_identity_and_dataset_source_swaps(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as db:
        db.add_all(
            [
                _album(20, black_player_id=1, white_player_id=3, event_id=10),
                _album(40, black_player_id=2, white_player_id=4, event_id=20),
                KifuSource(id=1, source_key="archive-a"),
                KifuSource(id=2, source_key="archive-b"),
                KifuAlbumSource(id=1, album_id=20, source_id=1, origin_path="a.sgf", match_method="import"),
                KifuAlbumSource(id=2, album_id=40, source_id=2, origin_path="b.sgf", match_method="import"),
            ]
        )
        db.commit()
    before = build_inventory(engine, batch_size=1)
    assert before["association_columns"] == [
        "id", "duplicate_of_id", "player_black", "player_white", "event",
        "round_name", "black_rank", "white_rank", "date_played",
        "black_player_id", "white_player_id", "event_id", "sources",
    ]
    assert before["inventory_format"] == 2
    assert before["source_link_columns"] == ["id", "source_id", "source_key", "origin_path", "match_method"]
    assert before["album_associations"][0] == [
        20, None, "甲某", "乙某", "棋赛", None, None, None, "1934-05-01",
        1, 3, 10, [[1, 1, "archive-a", "a.sgf", "import"]],
    ]

    with Session(engine) as db:
        first, second = db.get(KifuAlbum, 20), db.get(KifuAlbum, 40)
        first.black_player_id, second.black_player_id = second.black_player_id, first.black_player_id
        first.white_player_id, second.white_player_id = second.white_player_id, first.white_player_id
        first.event_id, second.event_id = second.event_id, first.event_id
        first_link, second_link = db.get(KifuAlbumSource, 1), db.get(KifuAlbumSource, 2)
        first_link.album_id, second_link.album_id = second_link.album_id, first_link.album_id
        db.commit()
    after = build_inventory(engine, batch_size=2)
    assert after["scopes"]["all"]["identity_ids"] == before["scopes"]["all"]["identity_ids"]
    assert after["source_stats"] == before["source_stats"]
    assert after["album_associations"] != before["album_associations"]
    assert after["album_associations"][0] == [
        20, None, "甲某", "乙某", "棋赛", None, None, None, "1934-05-01",
        2, 4, 20, [[2, 2, "archive-b", "b.sgf", "import"]],
    ]
    assert after["sha256"] != before["sha256"]


def test_sqlite_snapshot_does_not_change_with_concurrent_insert(tmp_path):
    engine = _engine(tmp_path)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    with Session(engine) as db:
        db.add_all([_album(20), _album(40)])
        db.commit()
    baseline = build_inventory(engine, batch_size=1)
    inserted = False

    def insert_after_first_batch(_conn, _cursor, statement, _parameters, _context, _executemany):
        nonlocal inserted
        if inserted or "FROM kifu_albums" not in statement or "LIMIT" not in statement.upper():
            return
        inserted = True
        other = sqlite3.connect(tmp_path / "albums.db")
        try:
            other.execute(
                "INSERT INTO kifu_albums (id, player_black, player_white, source_path, sgf_content) "
                "VALUES (60, 'new', 'new', '/new', '(;FF[4])')"
            )
            other.commit()
        finally:
            other.close()

    event.listen(engine, "after_cursor_execute", insert_after_first_batch)
    try:
        running = build_inventory(engine, batch_size=1)
    finally:
        event.remove(engine, "after_cursor_execute", insert_after_first_batch)
    assert inserted
    assert running["sha256"] == baseline["sha256"]
    assert running["album_associations"] == baseline["album_associations"]
    assert build_inventory(engine)["sha256"] != baseline["sha256"]


def test_cli_writes_safe_metadata_and_inventory_without_database_writes(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as db:
        db.add(_album(20))
        db.commit()
    output = tmp_path / "inventory.json"
    assert main(["--database-url", str(engine.url), "--output", str(output)]) == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["counts"] == {"all": 1, "visible": 1, "sample": 1}
    assert data["database_identifier"].startswith("sqlite:///")
    assert data["snapshot_time"].endswith("Z")
    assert data["sha256"] == build_inventory(engine)["sha256"]
    assert data["inventory_format"] == 2
    assert data["album_associations"] == [
        [20, None, "甲某", "乙某", "棋赛", None, None, None, "1934-05-01", None, None, None, []]
    ]
    with Session(engine) as db:
        assert db.query(KifuAlbum).count() == 1


def test_postgres_isolation_and_read_only_are_set_before_the_first_query():
    calls = []
    transaction_read_only = ["on"]

    class Result:
        def __init__(self, value=None):
            self.value = value

        def scalar_one(self):
            return self.value

        def all(self):
            return []

        def __iter__(self):
            return iter(())

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            calls.append("close")

        def execution_options(self, **options):
            calls.append(("execution_options", options))
            return self

        def begin(self):
            calls.append("begin")

        def exec_driver_sql(self, sql):
            calls.append(sql)
            return Result("repeatable read" if sql == "SHOW transaction_isolation" else transaction_read_only[0])

        def execute(self, _query):
            calls.append("SELECT albums or sources")
            return Result()

        def rollback(self):
            calls.append("rollback")

    engine = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"),
        connect=lambda: Connection(),
        url=SimpleNamespace(render_as_string=lambda **_kwargs: "postgresql://test"),
    )
    assert build_inventory(engine)["counts"] == {"all": 0, "visible": 0, "sample": 0}
    assert calls[:4] == [
        ("execution_options", {"isolation_level": "REPEATABLE READ", "postgresql_readonly": True}),
        "begin",
        "SHOW transaction_isolation",
        "SHOW transaction_read_only",
    ]
    assert calls.index("SHOW transaction_read_only") < calls.index("SELECT albums or sources")
    assert "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY" not in calls
    calls.clear()
    transaction_read_only[0] = "off"
    with pytest.raises(RuntimeError, match="REPEATABLE READ READ ONLY"):
        build_inventory(engine)
    assert "SELECT albums or sources" not in calls
    assert "rollback" in calls


def test_supplementary_and_compatibility_han_are_classified_as_han():
    assert _script_type("𠀀") == "han"
    assert _script_type("豈") == "han"
