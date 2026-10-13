"""Competition editions have stable IDs distinct from their event series."""

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from katrain.web.core import migrations, models_db


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def test_two_editions_and_rounds_share_one_competition_type(engine):
    models_db.Base.metadata.create_all(engine)
    assert "kifu_event_editions" in inspect(engine).get_table_names()

    with Session(engine, expire_on_commit=False) as db:
        series = models_db.KifuEvent(canonical_name="应氏杯")
        db.add(series)
        db.flush()
        first = models_db.KifuEventEdition(event_id=series.id, edition_number=1, year=1988)
        second = models_db.KifuEventEdition(event_id=series.id, edition_number=2, year=1992)
        db.add_all([first, second])
        db.flush()
        db.add_all([
            models_db.KifuAlbum(event_id=series.id, event_edition_id=first.id, round_name="半决赛",
                                player_black="甲", player_white="乙", sgf_content="(;)", source_path="first-a.sgf"),
            models_db.KifuAlbum(event_id=series.id, event_edition_id=first.id, round_name="决赛",
                                player_black="丙", player_white="丁", sgf_content="(;)", source_path="first-b.sgf"),
            models_db.KifuAlbum(event_id=series.id, event_edition_id=second.id, round_name="决赛",
                                player_black="戊", player_white="己", sgf_content="(;)", source_path="second.sgf"),
            models_db.KifuAlbum(event_id=series.id, event_edition_id=None, event="应氏杯（届次待核）",
                                player_black="庚", player_white="辛", sgf_content="(;)", source_path="unknown.sgf"),
        ])
        db.commit()

    with engine.connect() as conn:
        assert conn.execute(text("SELECT event_id, event_edition_id, round_name FROM kifu_albums "
                                 "ORDER BY id")).all() == [
            (series.id, first.id, "半决赛"),
            (series.id, first.id, "决赛"),
            (series.id, second.id, "决赛"),
            (series.id, None, None),
        ]


def test_edition_key_is_unique_within_type_but_not_by_year(engine):
    models_db.Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO kifu_events (id, canonical_name) VALUES (1, '应氏杯'), (2, '另一赛事')"))
        conn.execute(text("INSERT INTO kifu_event_editions (event_id, edition_number, year) "
                          "VALUES (1, 1, 1988), (1, 2, 1988), (2, 1, 1988)"))
        conn.execute(text("INSERT INTO kifu_event_editions (event_id, edition_label, year, season) "
                          "VALUES (1, '春季赛', 1988, 'spring')"))
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO kifu_event_editions (event_id, edition_number, year) "
                              "VALUES (1, 1, 1989)"))
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO kifu_event_editions (event_id, edition_label, year) "
                              "VALUES (1, '春季赛', 1989)"))


def test_year_only_and_year_season_are_valid_scoped_keys(engine):
    models_db.Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO kifu_events (id, canonical_name) VALUES (1, '赛事甲'), (2, '赛事乙')"))
        conn.execute(text("INSERT INTO kifu_event_editions (event_id, year, season) VALUES "
                          "(1, 2025, NULL), (1, 2025, 'spring'), (1, 2025, 'autumn'), (2, 2025, NULL)"))
    for duplicate in [(1, 2025, None), (1, 2025, "spring")]:
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO kifu_event_editions (event_id, year, season) "
                                  "VALUES (:event_id, :year, :season)"),
                             dict(zip(("event_id", "year", "season"), duplicate)))


def test_fresh_album_rejects_edition_from_another_competition(engine):
    models_db.Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO kifu_events (id, canonical_name) VALUES (1, '赛事甲'), (2, '赛事乙')"))
        conn.execute(text("INSERT INTO kifu_event_editions (id, event_id, year) VALUES (4, 2, 2025)"))
        conn.execute(text("INSERT INTO kifu_albums "
                          "(id, event_id, player_black, player_white, sgf_content, source_path) "
                          "VALUES (9, 1, '甲', '乙', '(;)', 'old.sgf')"))
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("UPDATE kifu_albums SET event_edition_id=4 WHERE id=9"))
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("UPDATE kifu_albums SET event_id=NULL, event_edition_id=4 WHERE id=9"))
    with engine.begin() as conn:
        conn.execute(text("UPDATE kifu_albums SET event_id=2, event_edition_id=4 WHERE id=9"))


def test_additive_migration_preserves_legacy_album_and_is_repeatable(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE kifu_events (id INTEGER PRIMARY KEY, canonical_name VARCHAR(256) NOT NULL)"))
        conn.execute(text("CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, event_id INTEGER "
                          "REFERENCES kifu_events(id), event VARCHAR(256), round_name VARCHAR(128), "
                          "sgf_content TEXT NOT NULL)"))
        conn.execute(text("INSERT INTO kifu_events VALUES (7, '应氏杯')"))
        conn.execute(text("INSERT INTO kifu_albums VALUES "
                          "(9, 7, '第一届应氏杯', '决赛', '(;EV[第一届应氏杯])')"))

    migrations.migrate_kifu_catalog_schema(engine)
    migrations.migrate_kifu_catalog_schema(engine)
    inspector = inspect(engine)
    assert "kifu_event_editions" in inspector.get_table_names()
    assert any(fk["constrained_columns"] == ["event_edition_id"] and
               fk["referred_table"] == "kifu_event_editions"
               for fk in inspector.get_foreign_keys("kifu_albums"))
    with engine.connect() as conn:
        assert conn.execute(text("SELECT event_id, event_edition_id, event, round_name, sgf_content "
                                 "FROM kifu_albums WHERE id=9")).one() == (
            7, None, "第一届应氏杯", "决赛", "(;EV[第一届应氏杯])"
        )
        assert conn.scalar(text("SELECT count(*) FROM kifu_event_editions")) == 0
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("UPDATE kifu_albums SET event_edition_id=999 WHERE id=9"))
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO kifu_events VALUES (8, '另一赛事')"))
        conn.execute(text("INSERT INTO kifu_event_editions (id, event_id, year) VALUES (4, 8, 2025)"))
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("UPDATE kifu_albums SET event_edition_id=4 WHERE id=9"))
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("UPDATE kifu_albums SET event_id=NULL, event_edition_id=4 WHERE id=9"))
    with engine.begin() as conn:
        conn.execute(text("UPDATE kifu_albums SET event_id=8, event_edition_id=4 WHERE id=9"))
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("UPDATE kifu_event_editions SET event_id=7 WHERE id=4"))


def test_postgres_edition_constraints_are_additive_and_not_valid():
    statements = migrations.postgres_kifu_album_edition_constraint_statements(
        existing_fks=set(), existing_checks=set()
    )
    assert any('FOREIGN KEY ("event_edition_id", "event_id")' in sql and 'NOT VALID' in sql
               for sql in statements)
    assert any('CHECK ("event_edition_id" IS NULL OR "event_id" IS NOT NULL) NOT VALID' in sql
               for sql in statements)
    assert migrations.postgres_kifu_album_edition_constraint_statements(
        existing_fks={"fk_kifu_albums_event_edition_type"},
        existing_checks={"ck_kifu_album_edition_requires_event"},
    ) == []


def test_migration_refuses_preexisting_cross_type_album_link(engine):
    models_db.Base.metadata.create_all(
        engine, tables=[models_db.KifuEvent.__table__, models_db.KifuEventEdition.__table__]
    )
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, event_id INTEGER "
                          "REFERENCES kifu_events(id), event_edition_id INTEGER "
                          "REFERENCES kifu_event_editions(id))"))
        conn.execute(text("INSERT INTO kifu_events (id, canonical_name) VALUES (1, '赛事甲'), (2, '赛事乙')"))
        conn.execute(text("INSERT INTO kifu_event_editions (id, event_id, year) VALUES (4, 2, 2025)"))
        conn.execute(text("INSERT INTO kifu_albums VALUES (9, 1, 4)"))
    with pytest.raises(RuntimeError, match="conflicts with competition type"):
        migrations.migrate_kifu_catalog_schema(engine)
