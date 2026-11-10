"""Album reads use bounded frozen rank overlays and preserve original fields."""

import asyncio
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from katrain.core.sgf_parser import SGF
from katrain.kifu_ingest.ranks import freeze_game_ranks, snapshot_sha256
from katrain.web.api.v1.endpoints import kifu
from katrain.web.core import models_db as m
from katrain.web.kifu.player_ranks import apply_rank_fact, build_source_rank_fact


WHEN = "2026-10-25T01:00:00+00:00"


def request():
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))


def source_fact(rank="7p", item="1", day="2026-10-01"):
    sgf = SGF.parse_sgf(f"(;PB[Black Player]PW[White Player]BR[{rank}]DT[{day}];B[aa])").sgf()
    game = {"source_key": "19x19", "source_item_id": item, "sgf_content": sgf}
    fact = build_source_rank_fact(
        canonical_name="Black Player",
        raw_rank=rank,
        sgf_content=sgf,
        slot="black",
        source_ref={"source_key": "19x19", "source_item_id": item},
        observed_at=WHEN,
    )
    return fact, game


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def album(db, *, raw=None, name="Black Player", fallback=True):
    player = m.KifuPlayer(canonical_name="Black Player")
    db.add(player)
    db.flush()
    fact, source = source_fact()
    fact_row = apply_rank_fact(db.connection(), player.id, fact, source_games=[source])
    sgf = SGF.parse_sgf(f"(;PB[{name}]PW[White Player]" + (f"BR[{raw}]" if raw is not None else "") + ";B[aa])").sgf()
    record = m.KifuAlbum(
        player_black=name,
        player_white="White Player",
        black_rank=raw,
        black_player_id=player.id,
        sgf_content=sgf,
        source_path="data/kifu-album/19x19/2.sgf",
        date_sort="2026-10-22",
    )
    db.add(record)
    db.flush()
    game = {
        "source_key": "19x19",
        "source_item_id": "2",
        "sgf_content": sgf,
        "sgf_sha256": sha256(sgf.encode()).hexdigest(),
        "identities": {"black": {"canonical_name": "Black Player"}},
        "metadata": {
            "player_black": name,
            "player_white": "White Player",
            "black_rank": raw,
            "white_rank": None,
        },
    }
    frozen = freeze_game_ranks(game, library_facts={"Black Player": fact} if fallback else {}, matched_at=WHEN)
    for side, snapshot in frozen["rank_snapshots"].items():
        db.add(
            m.KifuAlbumRankSnapshot(
                album_id=record.id,
                side=side,
                rank_fact_id=fact_row["rank_fact_id"] if side == "black" else None,
                snapshot=snapshot,
                snapshot_sha256=snapshot["content_sha256"],
                publication_key="synthetic",
                native_batch_id=1,
            )
        )
    db.commit()
    return record, frozen


def listing(db, lang="cn", **kwargs):
    return kifu.read_album_page(db, q=None, page=1, page_size=100, lang=lang, **kwargs)


def detail(db, album_id, lang="cn"):
    return asyncio.run(kifu.get_kifu_album(request(), album_id, lang=lang, db=db))


def test_frozen_fallback_is_identical_in_all_languages_list_preview_and_detail(db):
    record, frozen = album(db)
    for lang in ("cn", "tw", "jp", "ko", "en"):
        page = listing(db, lang)
        for value in (page.items[0], page.preview, detail(db, record.id, lang)):
            assert value.black_rank is None
            assert value.display_black_rank == "7p"
            assert value.black_rank_origin == "library_current"
            proof = value.black_rank_source
            assert proof["snapshot_sha256"] == frozen["rank_snapshots"]["black"]["content_sha256"]
            assert proof["source_ref"]["source_item_id"] == "2"
            assert proof["fact_source_ref"]["source_item_id"] == "1"
            assert "sgf_content" not in str(proof) and "evidence" not in proof
            assert value.display_white_rank == ""
            assert value.white_rank_origin == "unknown"
            assert value.white_rank_source["source_ref"]["slot"] == "white"


@pytest.mark.parametrize(
    "raw,name,expected",
    [
        ("9p", "Black Player", "9p"),
        ("9d", "Black Player", "9d"),
        ("6d", "Black Player", "6d"),
        ("6k", "Black Player", "6k"),
        ("七段", "Black Player", "七段"),
        (None, "棋手七段", "七段"),
        ("3002", "Black Player", ""),
    ],
)
def test_original_explicit_and_embedded_grades_win_and_raw_columns_stay_exact(db, raw, name, expected):
    record, _ = album(db, raw=raw, name=name)
    value = detail(db, record.id)
    assert value.display_black_rank == expected
    assert value.black_rank == raw
    assert value.black_rank_origin == "source"
    assert db.scalar(select(m.KifuAlbum.black_rank).where(m.KifuAlbum.id == record.id)) == raw


def test_unknown_rank_stays_empty_with_frozen_unknown_provenance(db):
    record, _ = album(db, fallback=False)
    value = detail(db, record.id)
    assert value.display_black_rank == ""
    assert value.black_rank is None
    assert value.black_rank_origin == "unknown"
    assert value.black_rank_source["rank_fact_sha256"] is None


def test_later_current_rank_never_changes_existing_snapshot_or_requires_history_read(db):
    record, frozen = album(db)
    fact, source = source_fact("8p", "3", "2026-10-23")
    apply_rank_fact(db.connection(), record.black_player_id, fact, source_games=[source])
    db.commit()
    statements = []
    event.listen(db.get_bind(), "before_cursor_execute", lambda _, __, sql, *args: statements.append(sql))
    assert detail(db, record.id).display_black_rank == "7p"
    assert (
        listing(db).preview.black_rank_source["snapshot_sha256"] == frozen["rank_snapshots"]["black"]["content_sha256"]
    )
    assert not any("kifu_player_rank_history" in sql for sql in statements)


@pytest.mark.parametrize("damage", ["hash", "row_hash", "slot", "sgf", "proof"])
def test_bad_snapshot_fails_closed_without_hiding_original_game(db, damage):
    record, _ = album(db)
    row = db.query(m.KifuAlbumRankSnapshot).filter_by(album_id=record.id, side="black").one()
    snapshot = deepcopy(row.snapshot)
    if damage == "hash":
        snapshot["display_rank"] = "8p"
    elif damage == "slot":
        snapshot["source_ref"]["slot"] = "white"
        snapshot["content_sha256"] = snapshot_sha256(snapshot)
    elif damage == "sgf":
        snapshot["source_ref"]["sgf_sha256"] = "a" * 64
        snapshot["content_sha256"] = snapshot_sha256(snapshot)
    elif damage == "proof":
        snapshot["source_proof"]["source_ref"]["capture_body"] = "private capture"
        snapshot["content_sha256"] = snapshot_sha256(snapshot)
    row.snapshot = snapshot
    row.snapshot_sha256 = "b" * 64 if damage == "row_hash" else snapshot["content_sha256"]
    db.commit()
    value = detail(db, record.id)
    assert value.id == record.id and value.black_rank is None
    assert value.display_black_rank == ""
    assert value.black_rank_origin == "unknown" and value.black_rank_source is None


def test_invalid_original_rank_without_snapshot_stays_source_and_never_displays_a_fallback(db):
    record, _ = album(db, raw="3002")
    db.query(m.KifuAlbumRankSnapshot).filter_by(album_id=record.id).delete()
    db.commit()
    value = detail(db, record.id)
    assert value.black_rank == "3002" and value.display_black_rank == ""
    assert value.black_rank_origin == "source" and value.black_rank_source is None


def test_page_loads_all_snapshot_rows_in_one_query_and_preview_reuses_them(db):
    for index in range(100):
        db.add(
            m.KifuAlbum(
                player_black="Black", player_white="White", sgf_content="(;B[aa])", source_path=f"fixture-{index}.sgf"
            )
        )
    db.commit()
    statements = []
    event.listen(db.get_bind(), "before_cursor_execute", lambda _, __, sql, *args: statements.append(sql))
    assert len(listing(db).items) == 100
    reads = [sql for sql in statements if "FROM kifu_album_rank_snapshots" in sql]
    assert len(reads) == 1
