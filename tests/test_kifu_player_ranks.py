"""Rank facts use portable provenance and do not rewrite raw album data."""

import importlib
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError

from katrain.web.core import models_db as m


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    m.Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            m.KifuPlayer.__table__.insert(), [{"id": 1, "canonical_name": "甲"}, {"id": 2, "canonical_name": "乙"}]
        )
    yield engine
    engine.dispose()


def ranks():
    return importlib.import_module("katrain.web.kifu.player_ranks")


def source_fact(rank="7p", day="2026-10-01", item="1", observed="2026-10-25T01:00:00+00:00"):
    sgf = f"(;FF[4]PB[甲]PW[乙]BR[{rank}]DT[{day}]SZ[19];B[aa])"
    game = {
        "source_key": "19x19",
        "source_item_id": item,
        "sgf_content": sgf,
        "metadata": {"player_black": "甲", "player_white": "乙", "black_rank": rank, "date_played": day},
    }
    fact = ranks().build_source_rank_fact(
        canonical_name="甲",
        raw_rank=rank,
        sgf_content=sgf,
        slot="black",
        source_ref={"source_key": "19x19", "source_item_id": item},
        observed_at=observed,
    )
    return fact, game


def apply(conn, fact, game):
    return ranks().apply_rank_fact(conn, 1, fact, source_games=[game])


def test_rank_schema_is_separate_and_current_unique_includes_conflicts(engine):
    tables = set(inspect(engine).get_table_names())
    assert {"kifu_player_rank_history", "kifu_album_rank_snapshots"} <= tables
    history = m.KifuPlayerRankHistory.__table__
    fact, game = source_fact()
    with engine.begin() as conn:
        row = apply(conn, fact, game)
        values = dict(conn.execute(select(history)).mappings().one())
        values.pop("id")
        values.update(content_sha256="a" * 64, status="conflict")
        with pytest.raises(IntegrityError):
            conn.execute(history.insert().values(**values))
        assert row["is_current"] is True
    assert "rank_value" not in m.KifuPlayer.__table__.columns
    assert "rank_snapshot" not in m.KifuAlbum.__table__.columns


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9p", (9, "professional_dan")),
        ("6d", (6, "amateur_dan")),
        ("6k", (6, "kyu")),
        ("七段", (7, "dan_unspecified")),
        ("初段", (1, "dan_unspecified")),
        ("业余六段", (6, "amateur_dan")),
        ("职业九段", (9, "professional_dan")),
        ("六级", (6, "kyu")),
    ],
)
def test_normalizer_preserves_typed_rank(raw, expected):
    parsed = ranks().normalize_rank(raw)
    assert (parsed["rank_value"], parsed["rank_system"]) == expected


@pytest.mark.parametrize("raw", [None, "", "3002", "0p", "10p", "99k", "七段老师八段", "foo9p"])
def test_normalizer_rejects_non_ranks(raw):
    assert ranks().normalize_rank(raw) is None


def test_identity_only_resolves_unspecified_system_never_changes_explicit_dan():
    assert ranks().normalize_rank("七段", professional_identity=True)["rank_system"] == "professional_dan"
    assert ranks().normalize_rank("9d", professional_identity=True) == {"rank_value": 9, "rank_system": "amateur_dan"}


def test_portable_fact_hash_excludes_retry_time_but_covers_grade_and_source():
    fact, _ = source_fact()
    retry, _ = source_fact(observed="2026-10-26T01:00:00+00:00")
    assert fact["content_sha256"] == retry["content_sha256"]
    assert fact["valid_from"] is None
    assert fact["source_as_of"] == "2026-10-01"
    assert ranks().validate_rank_fact(fact, canonical_name="甲") == fact
    changed = deepcopy(fact)
    changed["rank_value"] = 8
    with pytest.raises(ValueError):
        ranks().validate_rank_fact(changed)
    with pytest.raises(ValueError):
        ranks().validate_rank_fact(fact, canonical_name="乙")
    assert "player_id" not in str(fact)


def test_source_builder_does_not_invent_date_or_promotion_date():
    fact = ranks().build_source_rank_fact(
        canonical_name="甲",
        raw_rank="7p",
        sgf_content="(;PB[甲]PW[乙]BR[7p]DT[2026-10])",
        slot="black",
        source_ref={"source_key": "19x19", "source_item_id": "1"},
    )
    assert fact["source_as_of"] is None
    assert fact["valid_from"] is None
    with pytest.raises(ValueError, match="valid_from"):
        ranks().build_source_rank_fact(
            canonical_name="甲",
            raw_rank="7p",
            sgf_content="(;PB[甲]BR[7p]DT[2026-10-01])",
            slot="black",
            source_ref={"source_key": "19x19", "source_item_id": "1"},
            valid_from="2026-10-01",
        )


def test_source_builder_rejects_wrong_slot_and_cannot_use_metadata_only_rank():
    fact, game = source_fact()
    with pytest.raises(ValueError):
        ranks().build_source_rank_fact(
            canonical_name="甲",
            raw_rank="7p",
            sgf_content=game["sgf_content"].replace("BR[7p]", "BR[7p]WR[8p]"),
            slot="white",
            source_ref={"source_key": "19x19", "source_item_id": "1"},
        )
    assert (
        ranks().build_source_rank_fact(
            canonical_name="甲",
            raw_rank="7p",
            sgf_content="(;PB[甲]PW[乙])",
            slot="black",
            source_ref={"source_key": "19x19", "source_item_id": "1"},
        )
        is None
    )


def test_apply_deduplicates_and_preserves_first_observed_at(engine):
    fact, game = source_fact()
    retry, _ = source_fact(observed="2026-10-26T01:00:00+00:00")
    with engine.begin() as conn:
        a, b = apply(conn, fact, game), apply(conn, retry, game)
        assert a["rank_fact_id"] == b["rank_fact_id"]
        assert a["inserted"] and not b["inserted"]
        row = conn.execute(select(m.KifuPlayerRankHistory.__table__)).mappings().one()
        assert row["observed_at"].date().isoformat() == "2026-10-25"
        assert row["valid_from"] is None


def test_later_same_grade_is_new_observation_then_promotion_preserves_history(engine):
    with engine.begin() as conn:
        a, ga = source_fact()
        b, gb = source_fact(day="2026-10-02", item="2")
        c, gc = source_fact(rank="8p", day="2026-10-03", item="3")
        apply(conn, a, ga)
        apply(conn, b, gb)
        current = apply(conn, c, gc)
        rows = conn.execute(select(m.KifuPlayerRankHistory.__table__)).mappings().all()
        assert len(rows) == 3
        assert [row["rank_value"] for row in rows] == [7, 7, 8]
        assert [row["is_current"] for row in rows] == [False, False, True]
        assert current["status"] == "qualified"
        assert apply(conn, a, ga)["is_current"] is False


def test_late_uploaded_old_game_never_rolls_back_current(engine):
    with engine.begin() as conn:
        newer, ng = source_fact(rank="8p", day="2026-10-03", item="3")
        older, og = source_fact(rank="7p", day="2026-10-01")
        apply(conn, newer, ng)
        assert apply(conn, older, og)["is_current"] is False
        assert conn.scalar(select(m.KifuPlayerRankHistory.rank_value).where(m.KifuPlayerRankHistory.is_current)) == 8


@pytest.mark.parametrize(("rank", "day"), [("8p", "2026-10-01"), ("6p", "2026-10-02"), ("7d", "2026-10-02")])
def test_conflicting_grade_downgrade_or_system_makes_current_conflict(engine, rank, day):
    with engine.begin() as conn:
        fact, game = source_fact()
        apply(conn, fact, game)
        conflict, cg = source_fact(rank=rank, day=day, item="2")
        result = apply(conn, conflict, cg)
        assert result["status"] == "conflict" and result["is_current"]
        assert (
            conn.scalar(select(m.KifuPlayerRankHistory.status).where(m.KifuPlayerRankHistory.is_current)) == "conflict"
        )
    assert (
        ranks().lookup_library_rank_facts(engine, [{"id": 1, "canonical_name": "甲", "status": "qualified"}])[1][
            "status"
        ]
        == "conflict"
    )


def test_native_verifier_rejects_unbound_source_or_player(engine):
    fact, game = source_fact()
    with engine.begin() as conn:
        with pytest.raises(ValueError, match="source"):
            ranks().verify_rank_fact_for_player(conn, 1, fact)
        with pytest.raises(ValueError, match="owner|canonical"):
            ranks().verify_rank_fact_for_player(conn, 2, fact, source_games=[game])
        wrong = deepcopy(game)
        wrong["sgf_content"] = wrong["sgf_content"].replace("7p", "8p")
        with pytest.raises(ValueError):
            ranks().verify_rank_fact_for_player(conn, 1, fact, source_games=[wrong])


def test_snapshot_restrict_fk_and_batch_lookup(engine):
    with engine.begin() as conn:
        fact, game = source_fact()
        row = apply(conn, fact, game)
        conn.execute(
            m.KifuAlbum.__table__.insert().values(
                id=1, player_black="甲", player_white="乙", sgf_content=game["sgf_content"], source_path="one"
            )
        )
        conn.execute(
            m.KifuAlbumRankSnapshot.__table__.insert().values(
                album_id=1,
                side="black",
                rank_fact_id=row["rank_fact_id"],
                snapshot={"origin": "library_current"},
                snapshot_sha256="a" * 64,
                publication_key="pub",
                native_batch_id=1,
            )
        )
        snapshots = ranks().lookup_album_rank_snapshots(conn, [1])
        assert snapshots[(1, "black")]["snapshot"]["origin"] == "library_current"
        with pytest.raises(IntegrityError):
            conn.execute(m.KifuPlayerRankHistory.__table__.delete())


def test_existing_application_startup_never_creates_rank_tables(engine):
    from sqlalchemy.orm import sessionmaker
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core import migrations

    migrations.install_kifu_name_change_immutability(engine)
    migrations.create_kifu_name_indexes(engine)
    with engine.begin() as conn:
        m.KifuAlbumRankSnapshot.__table__.drop(conn)
        m.KifuPlayerRankHistory.__table__.drop(conn)
    SQLAlchemyUserRepository(sessionmaker(bind=engine)).init_db()
    assert "kifu_player_rank_history" not in inspect(engine).get_table_names()
    assert "kifu_album_rank_snapshots" not in inspect(engine).get_table_names()


def test_fresh_application_startup_also_requires_explicit_rank_migration():
    from sqlalchemy.orm import sessionmaker
    from katrain.web.core.auth import SQLAlchemyUserRepository

    empty = create_engine("sqlite:///:memory:")
    try:
        SQLAlchemyUserRepository(sessionmaker(bind=empty)).init_db()
        tables = set(inspect(empty).get_table_names())
        assert "kifu_player_names" in tables
        assert "kifu_player_rank_history" not in tables
        assert "kifu_album_rank_snapshots" not in tables
    finally:
        empty.dispose()


def test_startup_never_repairs_or_rebuilds_existing_partial_rank_schema(engine):
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core import migrations

    migrations.install_kifu_name_change_immutability(engine)
    migrations.create_kifu_name_indexes(engine)
    tables = {"kifu_player_rank_history": "player_id", "kifu_album_rank_snapshots": "album_id"}
    with engine.begin() as conn:
        m.KifuAlbumRankSnapshot.__table__.drop(conn)
        m.KifuPlayerRankHistory.__table__.drop(conn)
        for table, owner_column in tables.items():
            conn.exec_driver_sql(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, {owner_column} INTEGER)")
            conn.exec_driver_sql(f"INSERT INTO {table} (id, {owner_column}) VALUES (1, 1)")
    SQLAlchemyUserRepository(sessionmaker(bind=engine)).init_db()
    for table, owner_column in tables.items():
        assert {column["name"] for column in inspect(engine).get_columns(table)} == {"id", owner_column}
        assert inspect(engine).get_indexes(table) == []
        with engine.connect() as conn:
            assert conn.execute(text(f"SELECT * FROM {table}")).all() == [(1, 1)]


@pytest.mark.parametrize("older_rank", ["8p", "7d"])
@pytest.mark.parametrize("arrival_order", ["older_first", "newer_first"])
def test_late_old_evidence_marks_newer_current_conflict_without_replacing_fact(engine, older_rank, arrival_order):
    older, older_game = source_fact(rank=older_rank, day="2026-10-01", item="1")
    newer, newer_game = source_fact(rank="7p", day="2026-10-03", item="2")
    observations = [(older, older_game), (newer, newer_game)]
    if arrival_order == "newer_first":
        observations.reverse()
    with engine.begin() as conn:
        for fact, game in observations:
            apply(conn, fact, game)
        rows = conn.execute(select(m.KifuPlayerRankHistory.__table__)).mappings().all()
        assert len(rows) == 2
        assert {row["content_sha256"] for row in rows} == {older["content_sha256"], newer["content_sha256"]}
        current = next(row for row in rows if row["is_current"])
        assert current["content_sha256"] == newer["content_sha256"]
        assert current["rank_value"] == 7 and current["source_as_of"].isoformat() == "2026-10-03"
        assert current["status"] == "conflict"
        assert ranks().validate_rank_fact(ranks()._row_fact(current, "甲"))["content_sha256"] == newer["content_sha256"]
    assert (
        ranks().lookup_library_rank_facts(engine, [{"id": 1, "canonical_name": "甲", "status": "qualified"}])[1][
            "status"
        ]
        == "conflict"
    )


@pytest.mark.parametrize("unspecified_rank", ["七段", "九段"])
@pytest.mark.parametrize("arrival_order", ["older_first", "newer_first"])
def test_unspecified_system_is_not_a_cross_system_or_professional_downgrade_conflict(
    engine, unspecified_rank, arrival_order
):
    unspecified, ug = source_fact(rank=unspecified_rank, day="2026-10-01", item="1")
    typed, tg = source_fact(rank="8p", day="2026-10-03", item="2")
    observations = [(unspecified, ug), (typed, tg)]
    if arrival_order == "newer_first":
        observations.reverse()
    with engine.begin() as conn:
        for fact, game in observations:
            apply(conn, fact, game)
        current = (
            conn.execute(select(m.KifuPlayerRankHistory.__table__).where(m.KifuPlayerRankHistory.is_current))
            .mappings()
            .one()
        )
        assert current["content_sha256"] == typed["content_sha256"]
        assert current["rank_system"] == "professional_dan" and current["rank_value"] == 8
        assert current["status"] == "qualified"
    assert (
        ranks().lookup_library_rank_facts(engine, [{"id": 1, "canonical_name": "甲", "status": "qualified"}])[1][
            "status"
        ]
        == "qualified"
    )


def test_newer_unspecified_observation_cannot_replace_known_typed_current(engine):
    typed, tg = source_fact(rank="8p", day="2026-10-01", item="1")
    unspecified, ug = source_fact(rank="九段", day="2026-10-03", item="2")
    with engine.begin() as conn:
        apply(conn, typed, tg)
        added = apply(conn, unspecified, ug)
        assert added["inserted"] and not added["is_current"]
        rows = conn.execute(select(m.KifuPlayerRankHistory.__table__)).mappings().all()
        assert len(rows) == 2
        current = next(row for row in rows if row["is_current"])
        assert current["content_sha256"] == typed["content_sha256"]
        assert current["source_as_of"].isoformat() == "2026-10-01"
        assert current["status"] == "qualified"
    result = ranks().lookup_library_rank_facts(engine, [{"id": 1, "canonical_name": "甲", "status": "qualified"}])[1]
    assert result["status"] == "qualified"
    assert result["fact"]["rank_value"] == 8 and result["fact"]["rank_system"] == "professional_dan"


@pytest.mark.parametrize("arrival_order", ["older_first", "newer_first"])
def test_unspecified_dan_and_kyu_still_conflict_in_either_arrival_order(engine, arrival_order):
    dan, dg = source_fact(rank="七段", day="2026-10-01", item="1")
    kyu, kg = source_fact(rank="6k", day="2026-10-03", item="2")
    observations = [(dan, dg), (kyu, kg)]
    if arrival_order == "newer_first":
        observations.reverse()
    with engine.begin() as conn:
        for fact, game in observations:
            apply(conn, fact, game)
        current = (
            conn.execute(select(m.KifuPlayerRankHistory.__table__).where(m.KifuPlayerRankHistory.is_current))
            .mappings()
            .one()
        )
        assert current["content_sha256"] == kyu["content_sha256"]
        assert current["status"] == "conflict"


def test_newer_unspecified_dan_marks_known_kyu_conflict_without_overwriting_current(engine):
    kyu, kg = source_fact(rank="6k", day="2026-10-01", item="1")
    dan, dg = source_fact(rank="七段", day="2026-10-03", item="2")
    with engine.begin() as conn:
        apply(conn, kyu, kg)
        assert not apply(conn, dan, dg)["is_current"]
        current = (
            conn.execute(select(m.KifuPlayerRankHistory.__table__).where(m.KifuPlayerRankHistory.is_current))
            .mappings()
            .one()
        )
        assert current["content_sha256"] == kyu["content_sha256"]
        assert current["status"] == "conflict"


@pytest.mark.parametrize("typed_rank", ["8p", "8d"])
@pytest.mark.parametrize("newer_unspecified_rank", ["八段", "九段"])
@pytest.mark.parametrize("arrival_order", ["typed_first", "unspecified_first"])
def test_explicit_dan_refines_newer_unspecified_current_in_either_arrival_order(
    engine, typed_rank, newer_unspecified_rank, arrival_order
):
    typed, tg = source_fact(rank=typed_rank, day="2026-10-01", item="1")
    unspecified, ug = source_fact(rank=newer_unspecified_rank, day="2026-10-03", item="2")
    observations = [(typed, tg), (unspecified, ug)]
    if arrival_order == "unspecified_first":
        observations.reverse()
    with engine.begin() as conn:
        for fact, game in observations:
            apply(conn, fact, game)
        rows = conn.execute(select(m.KifuPlayerRankHistory.__table__)).mappings().all()
        assert len(rows) == 2
        current = next(row for row in rows if row["is_current"])
        assert current["content_sha256"] == typed["content_sha256"]
        assert current["rank_system"] == typed["rank_system"] and current["rank_value"] == 8
        assert current["source_as_of"].isoformat() == "2026-10-01"
        assert current["status"] == "qualified"
        raw_unknown = next(row for row in rows if row["content_sha256"] == unspecified["content_sha256"])
        assert raw_unknown["source_as_of"].isoformat() == "2026-10-03"
        assert raw_unknown["rank_system"] == "dan_unspecified"
        assert raw_unknown["rank_value"] == unspecified["rank_value"]
    result = ranks().lookup_library_rank_facts(engine, [{"id": 1, "canonical_name": "甲", "status": "qualified"}])[1]
    assert result["status"] == "qualified"
    assert result["fact"]["content_sha256"] == typed["content_sha256"]


@pytest.mark.parametrize("typed_rank", ["8p", "8d"])
@pytest.mark.parametrize("arrival_order", ["typed_first", "unspecified_first"])
@pytest.mark.parametrize("basis_day", ["2026-10-03", ""])
def test_same_basis_different_unspecified_grade_conflicts_and_stays_sticky(
    engine, typed_rank, arrival_order, basis_day
):
    typed, tg = source_fact(rank=typed_rank, day=basis_day, item="1")
    unspecified, ug = source_fact(rank="九段", day=basis_day, item="2")
    observations = [(typed, tg), (unspecified, ug)]
    if arrival_order == "unspecified_first":
        observations.reverse()
    with engine.begin() as conn:
        for fact, game in observations:
            apply(conn, fact, game)
        rows = conn.execute(select(m.KifuPlayerRankHistory.__table__)).mappings().all()
        assert len(rows) == 2
        current = next(row for row in rows if row["is_current"])
        assert current["content_sha256"] == typed["content_sha256"]
        assert current["rank_value"] == 8 and current["rank_system"] == typed["rank_system"]
        assert (current["source_as_of"].isoformat() if current["source_as_of"] else None) == typed["source_as_of"]
        assert current["evidence"] == typed["evidence"] and current["source_ref"] == typed["source_ref"]
        assert current["status"] == "conflict"
    assert (
        ranks().lookup_library_rank_facts(engine, [{"id": 1, "canonical_name": "甲", "status": "qualified"}])[1][
            "status"
        ]
        == "conflict"
    )
    later, lg = source_fact(rank="9" + typed_rank[-1], day="2026-10-04", item="3")
    with engine.begin() as conn:
        assert apply(conn, later, lg)["status"] == "conflict"
        current = (
            conn.execute(select(m.KifuPlayerRankHistory.__table__).where(m.KifuPlayerRankHistory.is_current))
            .mappings()
            .one()
        )
        assert current["content_sha256"] == later["content_sha256"] and current["rank_value"] == 9
    assert (
        ranks().lookup_library_rank_facts(engine, [{"id": 1, "canonical_name": "甲", "status": "qualified"}])[1][
            "status"
        ]
        == "conflict"
    )
