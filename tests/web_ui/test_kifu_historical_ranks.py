"""Historical ranks use original as-of sources and portable frozen decisions."""

from copy import deepcopy
from datetime import datetime

import pytest
from sqlalchemy import create_engine, select, update
from katrain.web.core import models_db as m

MATCHED = "2026-11-03T00:00:00+00:00"


@pytest.fixture
def conn():
    engine = create_engine("sqlite:///:memory:")
    m.Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            m.KifuPlayer.__table__.insert(),
            [{"id": 11, "canonical_name": "棋手甲"}, {"id": 12, "canonical_name": "棋手乙"}],
        )
        connection.execute(
            m.KifuSource.__table__.insert(), [{"id": 3, "source_key": "CWI"}, {"id": 4, "source_key": "19x19"}]
        )
        yield connection
    engine.dispose()


def game(conn, ident, day, rank, *, family="19x19", name="棋手甲", sgf=None):
    path = f"data/kifu-album/{'19x19' if family == '19x19' else 'Go_Seigen'}/{ident}.sgf"
    content = sgf or f"(;SZ[19]PB[{name}]PW[棋手乙]BR[{rank}]WR[1p]DT[{day}];B[aa];W[bb])"
    conn.execute(
        m.KifuAlbum.__table__.insert().values(
            id=ident,
            source_path=path,
            sgf_content=content,
            player_black=name,
            player_white="棋手乙",
            black_player_id=11,
            white_player_id=12,
            black_rank=rank,
            white_rank="1p",
            date_played=day,
            date_sort=day,
        )
    )
    conn.execute(
        m.KifuAlbumSource.__table__.insert().values(
            album_id=ident, source_id=4 if family == "19x19" else 3, origin_path=path, match_method="source_path"
        )
    )
    return target(conn, ident)


def target(conn, ident, side="black"):
    a = dict(conn.execute(select(m.KifuAlbum.__table__).where(m.KifuAlbum.id == ident)).mappings().one())
    links = [
        dict(r)
        for r in conn.execute(
            select(m.KifuAlbumSource.__table__, m.KifuSource.source_key)
            .join(m.KifuSource, m.KifuSource.id == m.KifuAlbumSource.source_id)
            .where(m.KifuAlbumSource.album_id == ident)
        ).mappings()
    ]
    return {"album": a, "side": side, "source_links": links}


def resolve(conn, entry):
    from katrain.web.kifu.historical_ranks import prepare_rank_decisions

    return prepare_rank_decisions(conn, [entry], matched_at=MATCHED)["decisions"][0]


@pytest.mark.parametrize(
    "prior_day,target_day,grade", [("1968-05-23", "1968-08-01", "9p"), ("1934-04-25", "1934-06-03", "5p")]
)
def test_missing_rank_uses_latest_original_as_of_game(conn, prior_day, target_day, grade):
    game(conn, 1, prior_day, grade)
    decision = resolve(conn, game(conn, 2, target_day, "", family="CWI"))
    assert decision["display_rank"] == grade
    assert decision["origin"] == "historical_prior"
    assert decision["basis"][0]["raw_date"] == prior_day
    assert decision["player_ref"] == {"canonical_name": "棋手甲"}


def test_bare_rank_refines_only_type_and_keeps_source_number(conn):
    game(conn, 1, "1950-01-01", "8p")
    decision = resolve(conn, game(conn, 2, "1968-08-01", "9d", family="CWI"))
    assert (decision["display_rank"], decision["origin"]) == ("9p", "historical_type")


@pytest.mark.parametrize(
    "rank,family,name,expected",
    [
        ("9d", "19x19", "棋手甲", "9d"),
        ("9d ama", "CWI", "棋手甲", "9d"),
        ("業餘九段", "CWI", "棋手甲", "9d"),
        ("3k", "CWI", "棋手甲", "3k"),
        ("", "CWI", "棋手甲九段", "9段"),
        ("9pro", "CWI", "棋手甲", "9p"),
    ],
)
def test_source_matrix_and_embedded_rank(conn, rank, family, name, expected):
    assert resolve(conn, game(conn, 1, "1934", rank, family=family, name=name))["display_rank"] == expected


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("future", "no_prior_original"),
        ("same_day", "same_day_conflict"),
        ("boundary", "typed_boundary"),
        ("decrease", "professional_grade_decrease"),
        ("partial", "untrusted_target_date"),
        ("upload", "untrusted_target_date"),
    ],
)
def test_historical_ambiguity_refuses_without_inventing_rank(conn, scenario, expected):
    day = "1968-08-01"
    if scenario == "future":
        game(conn, 1, "1969-01-01", "9p")
    else:
        game(conn, 1, "1960-01-01", "8p")
    raw = ""
    if scenario == "same_day":
        game(conn, 3, "1960-01-01", "7p")
    if scenario == "boundary":
        game(conn, 3, "1967-01-01", "9d")
        raw = "9d"
    if scenario == "decrease":
        raw = "7d"
    if scenario == "partial":
        day = "1968-08"
    if scenario == "upload":
        day = "2002-11-30"
    decision = resolve(conn, game(conn, 2, day, raw, family="CWI"))
    assert decision["refusal_reason"] == expected
    assert decision["display_rank"] == ("7段" if raw == "7d" else "9段" if raw else "")
    assert decision["origin"] in {"source", "unknown"}


@pytest.mark.parametrize("damage", ["root_rank", "root_owner", "root_date", "source", "owner", "sha", "name_conflict"])
def test_exact_original_evidence_cannot_be_forged(conn, damage):
    prior = game(conn, 1, "1960-01-01", "9p")
    target_entry = game(conn, 2, "1968-08-01", "", family="CWI")
    if damage == "source":
        conn.execute(update(m.KifuAlbumSource).where(m.KifuAlbumSource.album_id == 1).values(origin_path="wrong"))
    elif damage == "owner":
        conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == 1).values(black_player_id=12))
    elif damage == "sha":
        # The frozen basis is checked against exact bytes when locally bound.
        from katrain.web.kifu.historical_ranks import bind_rank_decision

        decision = resolve(conn, target_entry)
        conn.execute(
            update(m.KifuAlbum).where(m.KifuAlbum.id == 1).values(sgf_content=prior["album"]["sgf_content"] + " ")
        )
        with pytest.raises(ValueError, match="basis|source"):
            bind_rank_decision(conn, target_entry, decision)
        return
    else:
        original = prior["album"]["sgf_content"]
        replacements = {
            "root_rank": ("BR[9p]", "BR[8p]"),
            "root_owner": ("PB[棋手甲]", "PB[棋手乙]"),
            "root_date": ("DT[1960-01-01]", "DT[1959-01-01]"),
            "name_conflict": ("PB[棋手甲]", "PB[棋手甲八段]"),
        }
        before, after = replacements[damage]
        conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == 1).values(sgf_content=original.replace(before, after)))
    decision = resolve(conn, target_entry)
    assert decision["origin"] == "unknown"
    assert not decision["basis"]


def test_same_players_same_day_is_not_same_game_and_missing_keeps_as_of_origin(conn):
    game(conn, 1, "1968-08-01", "9p", sgf="(;PB[棋手甲]PW[棋手乙]BR[9p]WR[1p]DT[1968-08-01];B[cc])")
    result = resolve(conn, game(conn, 2, "1968-08-01", "", family="CWI"))
    assert result["origin"] == "historical_prior"
    assert "same_game" not in str(result)


def test_first_apply_rechecks_complete_material_cohort_but_ignores_future(conn):
    from katrain.web.kifu.historical_ranks import prepare_rank_decisions, verify_initial_rank_decisions

    game(conn, 1, "1960-01-01", "9p")
    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    decisions = prepare_rank_decisions(conn, [entry], matched_at=MATCHED)["decisions"]
    game(conn, 3, "1969-01-01", "1d")
    verify_initial_rank_decisions(conn, [entry], decisions)
    game(conn, 4, "1967-01-01", "8d")
    with pytest.raises(ValueError, match="qualification|cohort"):
        verify_initial_rank_decisions(conn, [entry], decisions)


def test_overflow_defers_entire_cohort_before_fetching_sgf(conn, monkeypatch):
    from katrain.web.kifu import historical_ranks as h

    game(conn, 1, "1960-01-01", "9p")
    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    monkeypatch.setattr(h, "MAX_SCALAR_ROWS", 1)
    result = h.prepare_rank_decisions(conn, [entry], matched_at=MATCHED)
    assert result["decisions"][0]["origin"] == "unknown"
    assert result["decisions"][0]["refusal_reason"] == "resource_deferred"


def test_portable_decision_does_not_depend_on_local_ids(conn):
    from katrain.web.kifu.historical_ranks import validate_rank_decision

    game(conn, 1, "1960-01-01", "9p")
    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    before = resolve(conn, entry)
    conn.execute(update(m.KifuAlbumSource).values(id=m.KifuAlbumSource.id + 100))
    conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == 1).values(id=101))
    conn.execute(update(m.KifuAlbumSource).where(m.KifuAlbumSource.album_id == 1).values(album_id=101))
    after = resolve(conn, entry)
    assert before == after
    validate_rank_decision(after)
    bad = deepcopy(after)
    bad["display_rank"] = "九段"
    from katrain.web.kifu.source_rank_normalization import snapshot_digest

    bad["content_sha256"] = snapshot_digest(bad)
    with pytest.raises(ValueError, match="display|canonical"):
        validate_rank_decision(bad)


def test_initial_recheck_rejects_target_and_owner_drift(conn):
    from katrain.web.kifu.historical_ranks import verify_initial_rank_decisions

    game(conn, 1, "1960-01-01", "9p")
    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    decision = resolve(conn, entry)
    conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == 2).values(black_player_id=12))
    with pytest.raises(ValueError, match="owner|target|binding"):
        verify_initial_rank_decisions(conn, [entry], [decision])


def _applied_snapshot(conn, entry, decision):
    from katrain.web.kifu.historical_ranks import bind_rank_decision

    binding = bind_rank_decision(conn, entry, decision)
    registry = conn.execute(
        m.KifuNameSourceRegistry.__table__.insert().values(
            version="historical-rank-as-of-v1", sha256="a" * 64, registry={}
        )
    ).inserted_primary_key[0]
    batch_id = conn.execute(
        m.KifuNameBatch.__table__.insert().values(
            bundle_sha256="b" * 64,
            inventory_sha256="c" * 64,
            source_registry_id=registry,
            status="applied",
            reviewed_artifact={"basis_bindings": [binding]},
        )
    ).inserted_primary_key[0]
    row_id = conn.execute(
        m.KifuAlbumRankSnapshot.__table__.insert().values(
            album_id=entry["album"]["id"],
            side=entry["side"],
            snapshot=decision,
            snapshot_sha256=decision["content_sha256"],
            publication_key="historical-repair:fixture",
            native_batch_id=batch_id,
        )
    ).inserted_primary_key[0]
    after = dict(
        conn.execute(select(m.KifuAlbumRankSnapshot.__table__).where(m.KifuAlbumRankSnapshot.id == row_id))
        .mappings()
        .one()
    )
    conn.execute(
        m.KifuNameChange.__table__.insert().values(
            batch_id=batch_id,
            sequence=1,
            target_table="kifu_album_rank_snapshots",
            target_row_id=row_id,
            before_image=None,
            after_image=after,
        )
    )
    return batch_id, binding


@pytest.mark.parametrize("key", ["album_id", "source_link_id", "source_id", "player_id"])
def test_applied_standalone_or_native_v3_basis_blocks_undo(conn, key):
    from katrain.web.kifu.historical_ranks import assert_retained_rank_basis

    game(conn, 1, "1960-01-01", "9p")
    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    batch_id, binding = _applied_snapshot(conn, entry, resolve(conn, entry))
    with pytest.raises(ValueError, match="dependency"):
        assert_retained_rank_basis(conn, [{key: binding["basis"][0][key]}])
    assert_retained_rank_basis(conn, [{"album_id": 999}])
    assert_retained_rank_basis(conn, [{"album_id": 1}], excluding_batch_ids=[batch_id])
    conn.execute(m.KifuAlbumRankSnapshot.__table__.delete())
    conn.execute(update(m.KifuNameBatch).where(m.KifuNameBatch.id == batch_id).values(status="undone"))
    assert_retained_rank_basis(conn, [{"album_id": 1}])


def test_missing_dependency_artifact_fails_closed(conn):
    from katrain.web.kifu.historical_ranks import assert_retained_rank_basis

    game(conn, 1, "1960-01-01", "9p")
    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    batch_id, _ = _applied_snapshot(conn, entry, resolve(conn, entry))
    conn.execute(update(m.KifuNameBatch).where(m.KifuNameBatch.id == batch_id).values(reviewed_artifact={}))
    with pytest.raises(ValueError, match="artifact"):
        assert_retained_rank_basis(conn, [{"album_id": 1}])


@pytest.mark.parametrize("damage", ["hidden_id", "bad_set", "untrue_latest", "untrue_guard"])
def test_nested_qualification_is_strictly_validated(conn, damage):
    from katrain.web.kifu.historical_ranks import validate_rank_decision
    from katrain.web.kifu.source_rank_normalization import snapshot_digest

    game(conn, 1, "1960-01-01", "9p")
    decision = resolve(conn, game(conn, 2, "1968-08-01", "", family="CWI"))
    q = decision["qualification"]
    if damage == "hidden_id":
        q["same_day_ranks"][0]["player_id"] = 11
    elif damage == "bad_set":
        q["same_day_ranks"] = [{"rank_value": 8, "rank_system": "amateur_dan"}]
    elif damage == "untrue_latest":
        q["latest_day"] = "1967-01-01"
    else:
        q["professional_max"] = 10
    decision["content_sha256"] = snapshot_digest(decision)
    with pytest.raises(ValueError, match="qualification|grade"):
        validate_rank_decision(decision)


def test_source_and_unknown_initial_decisions_do_not_upgrade_on_new_evidence(conn):
    from katrain.web.kifu.historical_ranks import verify_initial_rank_decisions

    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    unknown = resolve(conn, entry)
    game(conn, 1, "1960-01-01", "9p")
    verify_initial_rank_decisions(conn, [entry], [unknown])


def test_a_conflicting_scalar_outside_body_shortlist_refuses(conn, monkeypatch):
    from katrain.web.kifu import historical_ranks as h

    game(conn, 1, "1960-01-01", "9p")
    game(conn, 3, "1960-01-01", "8d")
    monkeypatch.setattr(h, "MAX_BODY_ROWS", 1)
    decision = resolve(conn, game(conn, 2, "1968-08-01", "", family="CWI"))
    assert decision["refusal_reason"] == "same_day_conflict"


def test_original_sgf_body_limit_is_preflighted(conn, monkeypatch):
    from katrain.web.kifu import historical_ranks as h

    game(conn, 1, "1960-01-01", "9p", sgf="(;PB[棋手甲]PW[棋手乙]BR[9p]WR[1p]DT[1960-01-01]C[" + "x" * 1000 + "])")
    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    monkeypatch.setattr(h, "MAX_SGF_BYTES", 200)
    assert resolve(conn, entry)["refusal_reason"] == "resource_deferred"


def test_bare_target_conflicting_grade_on_same_day_cannot_refine(conn):
    game(conn, 1, "1968-08-01", "8p")
    decision = resolve(conn, game(conn, 2, "1968-08-01", "9d", family="CWI"))
    assert decision["display_rank"] == "9段"
    assert decision["refusal_reason"] == "same_day_conflict"


@pytest.mark.parametrize("damage", ["rank_list", "ref_slot", "basis_raw", "origin", "null_ranks"])
def test_malformed_nested_values_raise_value_error(conn, damage):
    from katrain.web.kifu.historical_ranks import validate_rank_decision
    from katrain.web.kifu.source_rank_normalization import snapshot_digest

    game(conn, 1, "1960-01-01", "9p")
    decision = resolve(conn, game(conn, 2, "1968-08-01", "", family="CWI"))
    if damage == "rank_list":
        decision["qualification"]["same_day_ranks"] = 1
    elif damage == "ref_slot":
        decision["source_ref"]["slot"] = []
    elif damage == "origin":
        decision["origin"] = []
    elif damage == "null_ranks":
        decision["qualification"]["same_day_ranks"] = None
    else:
        decision["basis"][0]["raw_rank"] = []
        decision["basis"][0]["content_sha256"] = snapshot_digest(decision["basis"][0])
    decision["content_sha256"] = snapshot_digest(decision)
    with pytest.raises(ValueError):
        validate_rank_decision(decision)


def test_live_binding_checks_lengths_before_loading_changed_body(conn, monkeypatch):
    from katrain.web.kifu import historical_ranks as h

    game(conn, 1, "1960-01-01", "9p")
    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    decision = resolve(conn, entry)
    conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == 2).values(sgf_content="x" * 1000))
    monkeypatch.setattr(h, "MAX_SGF_BYTES", 200)
    with pytest.raises(ValueError, match="resource"):
        h.bind_rank_decision(conn, entry, decision)


def test_portable_hash_is_equal_when_owner_source_and_album_ids_all_differ(conn):
    game(conn, 1, "1960-01-01", "9p")
    game(conn, 2, "1968-08-01", "", family="CWI")
    original = resolve(conn, target(conn, 2))
    conn.execute(update(m.KifuPlayer).values(id=m.KifuPlayer.id + 100))
    conn.execute(update(m.KifuSource).values(id=m.KifuSource.id + 100))
    conn.execute(
        update(m.KifuAlbum).values(
            id=m.KifuAlbum.id + 100,
            black_player_id=m.KifuAlbum.black_player_id + 100,
            white_player_id=m.KifuAlbum.white_player_id + 100,
        )
    )
    conn.execute(
        update(m.KifuAlbumSource).values(
            id=m.KifuAlbumSource.id + 100,
            album_id=m.KifuAlbumSource.album_id + 100,
            source_id=m.KifuAlbumSource.source_id + 100,
        )
    )
    assert resolve(conn, target(conn, 102)) == original


def test_current_profile_and_inferred_snapshot_are_never_original_evidence(conn):
    entry = game(conn, 2, "1934-06-03", "", family="CWI")
    conn.execute(
        m.KifuPlayerRankHistory.__table__.insert().values(
            player_id=11,
            rank_value=9,
            rank_system="professional_dan",
            source_as_of=None,
            observed_at=datetime.fromisoformat(MATCHED),
            source_kind="explicit_album_rank",
            source_ref={},
            evidence={},
            content_sha256="a" * 64,
            status="qualified",
            is_current=True,
        )
    )
    conn.execute(
        m.KifuAlbumRankSnapshot.__table__.insert().values(
            album_id=2,
            side="white",
            snapshot={"rank_value": 9, "rank_system": "professional_dan"},
            snapshot_sha256="b" * 64,
            native_batch_id=1,
            publication_key="unrelated",
        )
    )
    assert resolve(conn, entry)["refusal_reason"] == "no_prior_original"


@pytest.mark.parametrize("boundary", ["validate", "initial", "bind"])
def test_unknown_cannot_invent_a_grade_even_with_recomputed_hash(conn, boundary):
    from katrain.web.kifu import historical_ranks as h
    from katrain.web.kifu.source_rank_normalization import snapshot_digest

    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    decision = resolve(conn, entry)
    assert decision["origin"] == "unknown" and decision["basis"] == []
    decision.update(rank_value=9, rank_system="professional_dan", display_rank="9p")
    decision["content_sha256"] = snapshot_digest(decision)
    with pytest.raises(ValueError, match="unknown"):
        if boundary == "validate":
            h.validate_rank_decision(decision)
        elif boundary == "initial":
            h.verify_initial_rank_decisions(conn, [entry], [decision])
        else:
            h.bind_rank_decision(conn, entry, decision)


@pytest.mark.parametrize("bare", ["7d", "9d"])
def test_nearer_incompatible_original_bare_grade_blocks_missing_rank(conn, bare):
    from katrain.web.kifu.historical_ranks import verify_initial_rank_decisions

    game(conn, 1, "1960-01-01", "8p")
    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    frozen = resolve(conn, entry)
    assert frozen["display_rank"] == "8p"
    game(conn, 3, "1967-01-01", bare, family="CWI")
    current = resolve(conn, entry)
    assert current["origin"] == "unknown" and current["display_rank"] == ""
    assert current["refusal_reason"] in {"professional_grade_decrease", "incompatible_bare_observation"}
    assert current["qualification"] != frozen["qualification"]
    # The same receiver-only new observation invalidates a frozen sender decision.
    with pytest.raises(ValueError, match="qualification|cohort"):
        verify_initial_rank_decisions(conn, [entry], [frozen])


def test_compatible_bare_grade_and_future_bare_contradiction_preserve_qualification(conn):
    from katrain.web.kifu.historical_ranks import verify_initial_rank_decisions

    game(conn, 1, "1960-01-01", "8p")
    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    frozen = resolve(conn, entry)
    game(conn, 3, "1967-01-01", "8d", family="CWI")
    game(conn, 4, "1969-01-01", "7d", family="CWI")
    assert resolve(conn, entry) == frozen
    verify_initial_rank_decisions(conn, [entry], [frozen])


def test_disposable_postgresql_initial_cohort_and_query_timeout_restore():
    """Opt-in proof owns a UUID schema; never writes shared/public tables."""
    import os
    from uuid import uuid4
    from sqlalchemy import text
    from katrain.web.kifu.historical_ranks import (
        bind_rank_decision,
        prepare_rank_decisions,
        verify_initial_rank_decisions,
    )

    dsn = os.getenv("KIFU_STANDARDIZATION_TEST_PG_DSN")
    if not dsn:
        pytest.skip("set KIFU_STANDARDIZATION_TEST_PG_DSN for disposable PostgreSQL verification")
    schema = "kifu_rank_" + uuid4().hex
    control = create_engine(dsn)
    with control.begin() as admin:
        admin.execute(text(f"CREATE SCHEMA {schema}"))
    pg = create_engine(dsn, connect_args={"options": f"-csearch_path={schema}"}, isolation_level="READ COMMITTED")
    try:
        m.Base.metadata.create_all(pg)
        with pg.begin() as setup:
            setup.execute(
                m.KifuPlayer.__table__.insert(),
                [{"id": 11, "canonical_name": "棋手甲"}, {"id": 12, "canonical_name": "棋手乙"}],
            )
            setup.execute(
                m.KifuSource.__table__.insert(), [{"id": 3, "source_key": "CWI"}, {"id": 4, "source_key": "19x19"}]
            )
            game(setup, 1, "1960-01-01", "8p")
            game(setup, 2, "1968-08-01", "", family="CWI")
        with pg.connect() as first:
            first.exec_driver_sql("SET LOCAL statement_timeout = '13s'")
            previous = first.exec_driver_sql("SHOW statement_timeout").scalar_one()
            entry = target(first, 2)
            frozen = prepare_rank_decisions(first, [entry], matched_at=MATCHED)["decisions"]
            assert first.exec_driver_sql("SHOW statement_timeout").scalar_one() == previous
            assert frozen[0]["display_rank"] == "8p"
            with pg.connect() as readonly:
                readonly.exec_driver_sql("SET TRANSACTION READ ONLY")
                readonly_entry = target(readonly, 2)
                readonly_decision = prepare_rank_decisions(readonly, [readonly_entry], matched_at=MATCHED)["decisions"][
                    0
                ]
                assert readonly_decision == frozen[0]
                binding = bind_rank_decision(readonly, readonly_entry, readonly_decision, lock=False)
                assert binding["target"]["album_id"] == 2 and binding["basis"][0]["album_id"] == 1
                assert readonly.exec_driver_sql("SHOW transaction_read_only").scalar_one() == "on"
            # Another committed connection's new original is visible at the
            # READ COMMITTED recheck after taking the relevant table locks.
            with pg.begin() as second:
                game(second, 3, "1967-01-01", "7d", family="CWI")
            with pytest.raises(ValueError, match="qualification|cohort"):
                verify_initial_rank_decisions(first, [entry], frozen)
            assert first.exec_driver_sql("SHOW statement_timeout").scalar_one() == previous
    finally:
        pg.dispose()
        with control.begin() as admin:
            admin.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        control.dispose()


def _derived_incoming(body, source_metadata=None):
    from katrain.kifu_ingest.preparation import derive_metadata

    path = "data/kifu-album/19x19/incoming.sgf"
    return {
        "album": {
            "id": None,
            "source_path": path,
            "sgf_content": body,
            "black_player_id": 11,
            "white_player_id": 12,
            **derive_metadata(body, source_metadata),
        },
        "side": "black",
        "source_links": [
            {
                "id": None,
                "album_id": None,
                "source_id": 4,
                "source_key": "19x19",
                "origin_path": path,
                "match_method": "source_path",
            }
        ],
    }


def test_native_deterministically_derived_embedded_rank_can_refine(conn):
    game(conn, 1, "1960-01-01", "9p")
    entry = _derived_incoming("(;PB[棋手甲九段]PW[棋手乙]EV[比赛]DT[1968-08-01];B[aa])")
    assert entry["album"]["black_rank"] == "九段"
    decision = resolve(conn, entry)
    assert decision["display_rank"] == "9p" and decision["origin"] == "historical_type"
    entry["album"]["black_rank"] = "八段"
    with pytest.raises(ValueError, match="root"):
        resolve(conn, entry)


@pytest.mark.parametrize(
    "root_rank,name,display,origin",
    [("9p", "棋手甲", "9p", "source"), ("", "棋手甲九段", "9段", "source"), ("", "棋手甲", "", "unknown")],
)
def test_source_date_cannot_replace_missing_root_date_for_inference(conn, root_rank, name, display, origin):
    from katrain.web.kifu.historical_ranks import bind_rank_decision, verify_initial_rank_decisions

    game(conn, 1, "1960-01-01", "9p")
    entry = _derived_incoming(
        f"(;PB[{name}]PW[棋手乙]BR[{root_rank}]EV[比赛];B[aa])",
        {"playTime": {"date": {"year": 1968, "month": 8, "day": 1}}},
    )
    assert entry["album"]["date_played"] == "1968-08-01"
    decision = resolve(conn, entry)
    assert (decision["display_rank"], decision["origin"]) == (display, origin)
    assert decision["target_date"] is None and decision["qualification"] is None and decision["basis"] == []
    if root_rank != "9p":
        assert decision["refusal_reason"] == "untrusted_target_date"
    verify_initial_rank_decisions(conn, [entry], [decision])
    bind_rank_decision(conn, entry, decision)


def test_source_date_without_original_dt_cannot_be_historical_basis(conn):
    game(conn, 1, "1960-01-01", "9p", sgf="(;PB[棋手甲]PW[棋手乙]BR[9p]WR[1p];B[aa])")
    decision = resolve(conn, game(conn, 2, "1968-08-01", "", family="CWI"))
    assert decision["origin"] == "unknown" and decision["basis"] == []
    assert decision["refusal_reason"] == "invalid_original_evidence"


def test_binding_can_omit_row_locks_for_readonly_preparation(conn):
    from katrain.web.kifu.historical_ranks import bind_rank_decision

    game(conn, 1, "1960-01-01", "9p")
    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    decision = resolve(conn, entry)
    assert bind_rank_decision(conn, entry, decision, lock=False) == bind_rank_decision(conn, entry, decision)


def test_shared_operation_caches_one_large_original_for_99_public_bindings(conn):
    from sqlalchemy import event
    from katrain.web.kifu import historical_ranks as h

    game(conn, 1, "1960-01-01", "9p", sgf="(;PB[棋手甲]PW[棋手乙]BR[9p]WR[1p]DT[1960-01-01]C[" + "x" * 131000 + "])")
    entries = [game(conn, ident, "1968-08-01", "", family="CWI") for ident in range(2, 101)]
    decisions = h.prepare_rank_decisions(conn, entries, matched_at=MATCHED)["decisions"]
    body_reads = []

    def record_body_read(connection, clause, multiparams, params, execution_options):
        columns = list(getattr(clause, "selected_columns", ()))
        if len(columns) == 1 and columns[0] is m.KifuAlbum.__table__.c.sgf_content:
            body_reads.append(params)

    event.listen(conn, "before_execute", record_body_read)
    try:
        resource = h.EvidenceBudget()
        h.verify_initial_rank_decisions(conn, entries, decisions, resource=resource)
        for entry, decision in zip(entries, decisions):
            h.bind_rank_decision(conn, entry, decision, resource=resource)
        assert len(body_reads) == 1
        assert resource.used_bytes <= h.MAX_BODY_BYTES
    finally:
        event.remove(conn, "before_execute", record_body_read)


def test_shared_budget_reserves_unique_body_before_fetch_and_never_resets(conn):
    from katrain.web.kifu import historical_ranks as h
    from sqlalchemy import event

    first = game(conn, 1, "1960-01-01", "9p")
    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    decision = resolve(conn, entry)
    resource = h.EvidenceBudget(max_bytes=len(entry["album"]["sgf_content"].encode()))
    body_reads = []

    def record_body_read(connection, clause, multiparams, params, execution_options):
        columns = list(getattr(clause, "selected_columns", ()))
        if len(columns) == 1 and columns[0] is m.KifuAlbum.__table__.c.sgf_content:
            body_reads.append(params)

    event.listen(conn, "before_execute", record_body_read)
    try:
        with pytest.raises(ValueError, match="resource"):
            h.bind_rank_decision(conn, entry, decision, resource=resource)
        assert body_reads == []
        assert resource.used_bytes == len(entry["album"]["sgf_content"].encode())
        assert resource.cached_body(first["album"]["id"]) is None
        assert not list(conn.execute(select(m.KifuAlbumRankSnapshot.id)))
    finally:
        event.remove(conn, "before_execute", record_body_read)


def test_budget_rejects_invalid_reservation_without_mutation_and_counts_provided_once():
    from katrain.web.kifu.historical_ranks import EvidenceBudget

    resource = EvidenceBudget(max_bytes=10)
    for invalid in (-1, True, 11):
        with pytest.raises(ValueError, match="resource|budget"):
            resource.reserve(invalid)
        assert resource.used_bytes == 0
    resource.remember_body("abc", album_id=1)
    resource.remember_body("abc", album_id=2)
    assert resource.used_bytes == 3 and resource.remaining_bytes == 7
    resource.reserve(3)
    resource.remember_body("def", album_id=3, reserved=True)
    assert resource.used_bytes == 6


def test_shared_cache_rechecks_same_length_original_sha_drift(conn):
    from katrain.web.kifu import historical_ranks as h

    original = game(conn, 1, "1960-01-01", "9p")
    entry = game(conn, 2, "1968-08-01", "", family="CWI")
    decision = resolve(conn, entry)
    resource = h.EvidenceBudget()
    h.bind_rank_decision(conn, entry, decision, resource=resource)
    conn.execute(
        update(m.KifuAlbum)
        .where(m.KifuAlbum.id == 1)
        .values(sgf_content=original["album"]["sgf_content"].replace("BR[9p]", "BR[8p]"))
    )
    with pytest.raises(ValueError, match="source|basis"):
        h.bind_rank_decision(conn, entry, decision, resource=resource)


def test_original_root_name_rank_conflict_cannot_disappear_behind_older_basis(conn):
    from katrain.web.kifu import historical_ranks as h

    game(conn, 1, "1960-01-01", "9p")
    entry = game(conn, 2, "1968-01-01", "", family="CWI")
    frozen = resolve(conn, entry)
    game(conn, 3, "1967-01-01", "8p", name="棋手甲七段")
    current = resolve(conn, entry)
    assert current["origin"] == "unknown" and current["display_rank"] == ""
    assert current["refusal_reason"] == "root_name_rank_conflict"
    assert current["qualification"]["original_rank_conflict"] is True
    with pytest.raises(ValueError, match="qualification|cohort"):
        h.verify_initial_rank_decisions(conn, [entry], [frozen])
    # Applied replay binds its original frozen source; it never reruns initial
    # qualification just because a newer conflicting observation now exists.
    assert h.bind_rank_decision(conn, entry, frozen)["target"]["snapshot_sha256"] == frozen["content_sha256"]
    assert frozen["display_rank"] == "9p"


def _incoming_rank_entry(day, rank, item):
    entry = _derived_incoming(f"(;PB[棋手甲]PW[棋手乙]BR[{rank}]EV[比赛]DT[{day}];B[aa])")
    path = f"data/kifu-album/19x19/{item}.sgf"
    entry["album"]["source_path"] = path
    entry["source_links"][0]["origin_path"] = path
    return entry


def test_initial_recheck_rejects_same_incoming_batch_original_contradiction(conn):
    from katrain.web.kifu import historical_ranks as h

    game(conn, 1, "1960-01-01", "7p")
    source = _incoming_rank_entry("1967-01-01", "9d", "source")
    missing = _incoming_rank_entry("1967-02-01", "", "missing")
    decisions = h.prepare_rank_decisions(conn, [source, missing], matched_at=MATCHED)["decisions"]
    assert decisions[0]["display_rank"] == "9d" and decisions[0]["origin"] == "source"
    assert decisions[1]["display_rank"] == "7p"
    with pytest.raises(ValueError, match="incoming|qualification|cohort"):
        h.verify_initial_rank_decisions(conn, [source, missing], decisions)
    # Legacy frozen source slots can be supplied solely as disqualifiers,
    # without pretending they carry a new v3 snapshot.
    with pytest.raises(ValueError, match="incoming|qualification|cohort"):
        h.verify_initial_rank_decisions(conn, [missing], [decisions[1]], incoming_targets=[source, missing])


@pytest.mark.parametrize("day,rank", [("1969-01-01", "9d"), ("1967-01-01", ""), ("1967-01-01", "7p")])
def test_incoming_future_inferred_or_compatible_original_does_not_change_frozen_basis(conn, day, rank):
    from katrain.web.kifu import historical_ranks as h

    game(conn, 1, "1960-01-01", "7p")
    other = _incoming_rank_entry(day, rank, "other")
    missing = _incoming_rank_entry("1968-02-01", "", "missing")
    decisions = h.prepare_rank_decisions(conn, [other, missing], matched_at=MATCHED)["decisions"]
    original_hash = decisions[1]["content_sha256"]
    h.verify_initial_rank_decisions(conn, [other, missing], decisions)
    assert decisions[1]["basis"][0]["raw_date"] == "1960-01-01"
    assert decisions[1]["content_sha256"] == original_hash


def test_earlier_incoming_higher_professional_grade_still_blocks_decrease(conn):
    from katrain.web.kifu import historical_ranks as h

    game(conn, 1, "1960-01-01", "7p")
    earlier = _incoming_rank_entry("1950-01-01", "9p", "earlier")
    missing = _incoming_rank_entry("1968-02-01", "", "missing")
    decisions = h.prepare_rank_decisions(conn, [earlier, missing], matched_at=MATCHED)["decisions"]
    assert decisions[1]["display_rank"] == "7p"
    with pytest.raises(ValueError, match="incoming.*professional|grade.*decrease"):
        h.verify_initial_rank_decisions(conn, [earlier, missing], decisions)


def test_root_literals_parse_once_per_body_across_shared_operation(conn, monkeypatch):
    from collections import Counter
    from hashlib import sha256
    from katrain.web.kifu import historical_ranks as h

    game(conn, 1, "1960-01-01", "9p")
    entries = [game(conn, ident, "1968-08-01", "", family="CWI") for ident in (2, 3)]
    original_parse = h.SGF.parse_sgf
    parsed = Counter()

    def parse_once(body):
        parsed[sha256(body.encode()).hexdigest()] += 1
        return original_parse(body)

    monkeypatch.setattr(h.SGF, "parse_sgf", parse_once)
    resource = h.EvidenceBudget()
    decisions = h.prepare_rank_decisions(conn, entries, matched_at=MATCHED, resource=resource)["decisions"]
    h.verify_initial_rank_decisions(conn, entries, decisions, resource=resource)
    for entry, decision in zip(entries, decisions):
        h.bind_rank_decision(conn, entry, decision, resource=resource)
    assert parsed and set(parsed.values()) == {1}
    used = resource.used_bytes
    # A new operation owns a new cache and charges its bodies independently.
    fresh = h.EvidenceBudget()
    h.bind_rank_decision(conn, entries[0], decisions[0], resource=fresh)
    assert max(parsed.values()) == 2 and fresh.used_bytes > 0 and resource.used_bytes == used


def test_cached_root_literals_still_validate_fresh_database_metadata(conn, monkeypatch):
    from katrain.web.kifu import historical_ranks as h

    entry = game(conn, 1, "1968-08-01", "9pro")
    original_parse = h.SGF.parse_sgf
    parses = []

    def count(body):
        parses.append(True)
        return original_parse(body)

    monkeypatch.setattr(h.SGF, "parse_sgf", count)
    resource = h.EvidenceBudget()
    decision = h.prepare_rank_decisions(conn, [entry], matched_at=MATCHED, resource=resource)["decisions"][0]
    conn.execute(update(m.KifuAlbum).where(m.KifuAlbum.id == 1).values(black_rank="8pro"))
    with pytest.raises(ValueError, match="root.*grade"):
        h.bind_rank_decision(conn, entry, decision, resource=resource)
    assert len(parses) == 1


def test_metadata_cache_cannot_skip_body_budget_or_preserve_invalid_acceptance(conn):
    from katrain.web.kifu import historical_ranks as h

    entry = game(conn, 1, "1968-08-01", "9pro")
    album = entry["album"]
    with pytest.raises(ValueError, match="resource"):
        h.validate_rank_source_metadata(album, resource=h.EvidenceBudget(max_bytes=1))
    resource = h.EvidenceBudget()
    invalid = {**album, "black_rank": "8pro"}
    with pytest.raises(ValueError, match="root.*grade"):
        h.validate_rank_source_metadata(invalid, resource=resource)
    assert h.validate_rank_source_metadata(album, resource=resource)["raw_ranks"]["black"] == "9pro"
    with pytest.raises(ValueError, match="root.*grade"):
        h.validate_rank_source_metadata(invalid, resource=resource)
