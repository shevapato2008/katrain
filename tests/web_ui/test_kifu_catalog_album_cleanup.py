import copy

import pytest
from sqlalchemy import create_engine, text

from katrain.web.kifu.catalog_album_cleanup import capture, run


@pytest.fixture
def engine():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        for ddl in (
            "CREATE TABLE kifu_players (id INTEGER PRIMARY KEY, canonical_name TEXT)",
            "CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, duplicate_of_id INTEGER REFERENCES kifu_albums(id), "
            "player_black TEXT, player_white TEXT, black_rank TEXT, white_rank TEXT, black_player_id INTEGER, "
            "white_player_id INTEGER, event TEXT, result TEXT, round_name TEXT, date_played TEXT, place TEXT, source TEXT, "
            "source_path TEXT, sgf_content TEXT, search_text TEXT)",
            "CREATE TABLE kifu_album_sources (id INTEGER PRIMARY KEY, album_id INTEGER REFERENCES kifu_albums(id), source_id INTEGER)",
            "CREATE TABLE kifu_dedup_changes (id INTEGER PRIMARY KEY, album_id INTEGER REFERENCES kifu_albums(id), "
            "duplicate_of_id_before INTEGER REFERENCES kifu_albums(id), duplicate_of_id_after INTEGER REFERENCES kifu_albums(id))",
            "CREATE TABLE kifu_album_event_selections (album_id INTEGER PRIMARY KEY REFERENCES kifu_albums(id), selected_raw TEXT)",
            "CREATE TABLE kifu_analysis_jobs (id INTEGER PRIMARY KEY, album_id INTEGER REFERENCES kifu_albums(id), status TEXT)",
            "CREATE TABLE kifu_analysis_moves (id INTEGER PRIMARY KEY, job_id INTEGER REFERENCES kifu_analysis_jobs(id), move_number INTEGER)",
        ):
            conn.execute(text(ddl))
        conn.execute(text("INSERT INTO kifu_players VALUES (10,'Real'),(11,'Other')"))
        conn.execute(text("INSERT INTO kifu_albums (id,player_black,player_white,sgf_content,source_path,search_text) VALUES "
                          "(1,'Unknown','Real','(;PB[Unknown]PW[Real];B[dd])','one.sgf','unknown real'),"
                          "(2,'Unknown','Other','(;PB[Real]PW[Other];B[pp])','two.sgf','unknown other'),"
                          "(3,'Real','Other','(;PB[Real]PW[Other];B[qq])','three.sgf','real other')"))
        conn.execute(text("INSERT INTO kifu_album_sources VALUES (1,1,9)"))
        conn.execute(text("INSERT INTO kifu_dedup_changes VALUES (1,1,NULL,NULL)"))
        conn.execute(text("INSERT INTO kifu_album_event_selections VALUES (1,'Event')"))
        conn.execute(text("INSERT INTO kifu_analysis_jobs VALUES (1,1,'completed')"))
        conn.execute(text("INSERT INTO kifu_analysis_moves VALUES (1,1,1)"))
    yield engine
    engine.dispose()


def test_delete_one_sided_source_placeholder_with_all_children(engine):
    plan = capture(engine, [1])
    assert {key: len(rows) for key, rows in plan["snapshot"]["dependencies"].items()} == {
        "kifu_album_sources": 1, "kifu_dedup_changes": 1, "kifu_album_event_selections": 1,
        "kifu_analysis_jobs": 1, "kifu_analysis_moves": 1,
    }
    assert run(engine, plan)["committed"] is False
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM kifu_albums")) == 3
    result = run(engine, plan, apply=True)
    assert result["deleted"] == 1
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM kifu_albums")) == 2
        for table in plan["snapshot"]["dependencies"]:
            assert conn.scalar(text(f"SELECT count(*) FROM {table}")) == 0


def test_source_real_names_block_deletion_even_when_import_fields_unknown(engine):
    with pytest.raises(ValueError, match="two real player names"):
        capture(engine, [2])


@pytest.mark.parametrize("literal", ["???", "初段"])
def test_observed_nameless_source_literals_are_deletable(engine, literal):
    with engine.begin() as conn:
        conn.execute(text("UPDATE kifu_albums SET sgf_content=:sgf WHERE id=1"),
                     {"sgf": f"(;PB[{literal}]PW[Real];B[dd])"})
    plan = capture(engine, [1])
    assert run(engine, plan, apply=True)["deleted"] == 1


def test_bracketed_malformed_source_is_preserved(engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE kifu_albums SET sgf_content='(;PB[Unknown\\]]PW[Real])' WHERE id=1"))
    with pytest.raises(ValueError, match="malformed source player brackets"):
        capture(engine, [1])


def test_broken_pb_delimiter_is_preserved(engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE kifu_albums SET sgf_content='(;PB]PW[Real])' WHERE id=1"))
    with pytest.raises(ValueError, match="malformed source player brackets"):
        capture(engine, [1])


def test_patch_changes_only_names_ranks_fk_and_search(engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE kifu_albums SET result='B+R' WHERE id=3"))
    patch = {"id": 3, "player_black": "Real", "black_rank": "9p", "black_player_id": 10,
             "black_player_name": "Real", "white_player_id": 11, "white_player_name": "Other"}
    plan = capture(engine, [1], [patch])
    original = next(row for row in plan["snapshot"]["albums"] if row["id"] == 3)
    result = run(engine, plan, apply=True)
    assert result["updated"] == 1 and result["rank_changes"] == 1
    with engine.connect() as conn:
        changed = dict(conn.execute(text("SELECT * FROM kifu_albums WHERE id=3")).mappings().one())
    assert changed["black_rank"] == "9p" and changed["black_player_id"] == 10
    assert changed["white_player_id"] == 11 and "9p" in changed["search_text"]
    assert "b+r" in changed["search_text"]
    for field in ("sgf_content", "event", "date_played", "source_path", "source", "duplicate_of_id"):
        assert changed[field] == original[field]


def test_dependency_drift_aborts_everything(engine):
    plan = capture(engine, [1], [{"id": 3, "black_rank": "9p"}])
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO kifu_album_sources VALUES (2,1,10)"))
    with pytest.raises(ValueError, match="preimage drift"):
        run(engine, plan, apply=True)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM kifu_albums")) == 3
        assert conn.scalar(text("SELECT black_rank FROM kifu_albums WHERE id=3")) is None


def test_surviving_duplicate_reference_aborts(engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE kifu_albums SET duplicate_of_id=1 WHERE id=3"))
    with pytest.raises(ValueError, match="surviving albums"):
        capture(engine, [1])


def test_tampered_plan_and_failure_after_patch_roll_back(engine):
    plan = capture(engine, [1], [{"id": 3, "black_rank": "9p"}])
    tampered = copy.deepcopy(plan)
    tampered["delete_ids"] = [2]
    with pytest.raises(ValueError, match="SHA mismatch"):
        run(engine, tampered, apply=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TRIGGER reject_delete BEFORE DELETE ON kifu_albums "
                          "BEGIN SELECT RAISE(ABORT, 'injected failure'); END"))
    with pytest.raises(Exception, match="injected failure"):
        run(engine, plan, apply=True)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT black_rank FROM kifu_albums WHERE id=3")) is None
        assert conn.scalar(text("SELECT count(*) FROM kifu_album_sources")) == 1
