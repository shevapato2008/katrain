"""Read-only, reproducible inventory of raw kifu name inputs."""

import hashlib
import json
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from katrain.web.core.db import Base
from katrain.web.core.models_db import KifuAlbum, KifuAlbumSource, KifuSource
from katrain.web.kifu.name_inventory import build_inventory
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
        "black_player_id", "white_player_id", "event_id", "sources",
    ]
    assert before["source_link_columns"] == ["id", "source_id", "source_key", "origin_path", "match_method"]
    assert before["album_associations"][0] == [
        20, None, "甲某", "乙某", "棋赛", 1, 3, 10, [[1, 1, "archive-a", "a.sgf", "import"]],
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
        20, None, "甲某", "乙某", "棋赛", 2, 4, 20, [[2, 2, "archive-b", "b.sgf", "import"]],
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
    assert data["album_associations"] == [[20, None, "甲某", "乙某", "棋赛", None, None, None, []]]
    with Session(engine) as db:
        assert db.query(KifuAlbum).count() == 1
