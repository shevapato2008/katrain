import copy

import pytest
from sqlalchemy import create_engine, text

from katrain.web.kifu.player_existing3_exact import COUNTS, TARGETS, capture, digest, run, snapshot


@pytest.fixture
def prepared():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for sql in (
            "CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, player_black TEXT, player_white TEXT, black_player_id INTEGER, white_player_id INTEGER, sgf_content TEXT)",
            "CREATE TABLE kifu_players (id INTEGER PRIMARY KEY, canonical_name TEXT)",
            "CREATE TABLE kifu_player_aliases (id INTEGER PRIMARY KEY, player_id INTEGER, alias TEXT)",
            "CREATE TABLE kifu_player_names (id INTEGER PRIMARY KEY, player_id INTEGER, display_name TEXT)",
            "CREATE TABLE kifu_raw_player_values (id INTEGER PRIMARY KEY, raw_value TEXT, review_status TEXT, review_metadata JSON)",
            "CREATE TABLE kifu_album_sources (id INTEGER PRIMARY KEY, album_id INTEGER, source_id INTEGER)",
        ):
            c.execute(text(sql))
        album_id = 0
        for i, (raw, counts) in enumerate(COUNTS.items(), 1):
            c.execute(text("INSERT INTO kifu_players VALUES (:id,:raw)"), {"id": TARGETS[raw]["test"], "raw": raw})
            c.execute(
                text("INSERT INTO kifu_raw_player_values VALUES (:id,:raw,'pending',NULL)"), {"id": i, "raw": raw}
            )
            for _ in range(counts):
                album_id += 1
                c.execute(
                    text("INSERT INTO kifu_albums VALUES (:id,:raw,'opponent',NULL,9,'(;PB[x])')"),
                    {"id": album_id, "raw": raw},
                )
    yield engine, capture(engine, "test", "a" * 64)
    engine.dispose()


def test_dry_run_rolls_back_and_apply_only_links_and_reviews(prepared):
    engine, plan = prepared
    assert run(engine, "test", plan)["committed"] is False
    with engine.connect() as c:
        assert snapshot(c, "test") == plan["snapshot"]
    assert (
        run(engine, "test", plan, apply=True, plan_sha256="b" * 64, approved_plan_sha256="b" * 64)["created_player_ids"]
        == []
    )
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM kifu_players")) == 3
        assert (
            c.scalar(text("SELECT count(*) FROM kifu_albums WHERE black_player_id IS NOT NULL AND white_player_id=9"))
            == 407
        )
        assert c.scalar(text("SELECT count(*) FROM kifu_raw_player_values WHERE review_status='approved'")) == 3


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE kifu_albums SET sgf_content='changed' WHERE id=1",
        "UPDATE kifu_players SET canonical_name='other' WHERE id=353",
    ],
)
def test_stale_preimage_rejected_without_writes(prepared, sql):
    engine, plan = prepared
    with engine.begin() as c:
        c.execute(text(sql))
    with pytest.raises(ValueError, match="live preimage"):
        run(engine, "test", plan)
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM kifu_albums WHERE black_player_id IS NOT NULL")) == 0


def test_target_id_mismatch_rejected(prepared):
    engine, plan = prepared
    bad = copy.deepcopy(plan)
    bad["snapshot"]["slots"][0][3] = 999
    bad["snapshot_sha256"] = digest(bad["snapshot"])
    with pytest.raises(ValueError, match="membership/target"):
        run(engine, "test", bad)


def test_failure_after_album_updates_rolls_back(prepared):
    engine, plan = prepared
    with engine.begin() as c:
        c.execute(
            text(
                "CREATE TRIGGER reject_review BEFORE UPDATE ON kifu_raw_player_values BEGIN SELECT RAISE(ABORT, 'injected failure'); END"
            )
        )
    with pytest.raises(Exception, match="injected failure"):
        run(engine, "test", plan, apply=True, plan_sha256="b" * 64, approved_plan_sha256="b" * 64)
    with engine.connect() as c:
        assert snapshot(c, "test") == plan["snapshot"]
