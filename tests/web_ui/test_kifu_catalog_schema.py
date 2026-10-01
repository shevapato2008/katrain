"""The catalog schema must preserve old SGFs and enforce real relationships."""

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from katrain.web.core import migrations, models_db
from katrain.web.core.auth import SQLAlchemyUserRepository


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def test_fresh_catalog_has_distinct_entities_aliases_names_and_source_constraints(engine):
    models_db.Base.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())
    assert {
        "kifu_players", "kifu_events", "kifu_player_aliases", "kifu_event_aliases",
        "kifu_player_names", "kifu_event_names", "kifu_sources", "kifu_album_sources",
        "kifu_dedup_batches", "kifu_dedup_changes",
    } <= tables
    assert {"black_player_id", "white_player_id", "event_id", "duplicate_of_id"} <= {
        column["name"] for column in inspect(engine).get_columns("kifu_albums")
    }
    assert {fk["referred_table"] for fk in inspect(engine).get_foreign_keys("kifu_albums")} >= {
        "kifu_players", "kifu_events", "kifu_albums"
    }

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO kifu_players (id, canonical_name) VALUES (1, '吴清源'), (2, '同名者')"))
        conn.execute(text("INSERT INTO kifu_player_aliases (player_id, alias, normalized_alias) VALUES "
                          "(1, 'Go Seigen', 'go seigen'), (2, 'Go Seigen', 'go seigen')"))
        conn.execute(text("INSERT INTO kifu_player_names (player_id, lang, display_name, status) "
                          "VALUES (1, 'en', 'Go Seigen', 'verified')"))
        conn.execute(text("INSERT INTO kifu_sources (id, source_key) VALUES (1, 'cwi')"))
        conn.execute(text("INSERT INTO kifu_albums "
                          "(id, player_black, player_white, sgf_content, source_path) "
                          "VALUES (1, '吴清源', '木谷实', '(;FF[4])', 'old.sgf')"))
        conn.execute(text("INSERT INTO kifu_album_sources (album_id, source_id, origin_path, match_method) "
                          "VALUES (1, 1, 'old.sgf', 'original_path')"))

    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO kifu_player_names (player_id, lang, display_name, status) "
                              "VALUES (1, 'en', 'duplicate', 'review')"))
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO kifu_album_sources (album_id, source_id, origin_path, match_method) "
                              "VALUES (1, 1, 'old.sgf', 'manual')"))
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO kifu_album_sources (album_id, source_id, origin_path, match_method) "
                              "VALUES (999, 1, 'missing.sgf', 'manual')"))


def test_legacy_sqlite_catalog_migrates_without_rebuilding_or_changing_sgf(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, player_black VARCHAR(512) NOT NULL, "
                          "player_white VARCHAR(512) NOT NULL, sgf_content TEXT NOT NULL, "
                          "source_path VARCHAR(512) NOT NULL UNIQUE, source VARCHAR(256))"))
        conn.execute(text("INSERT INTO kifu_albums VALUES "
                          "(7, '吴清源', '木谷实', '(;FF[4]PB[吴清源]SO[CWI])', 'archive/7.sgf', 'SO value')"))
    repository = SQLAlchemyUserRepository(sessionmaker(bind=engine))
    repository.init_db()
    repository.init_db()

    foreign_keys = inspect(engine).get_foreign_keys("kifu_albums")
    assert {(fk["constrained_columns"][0], fk["referred_table"]) for fk in foreign_keys} >= {
        ("black_player_id", "kifu_players"), ("white_player_id", "kifu_players"),
        ("event_id", "kifu_events"), ("duplicate_of_id", "kifu_albums"),
    }
    with engine.connect() as conn:
        assert conn.execute(text("SELECT player_black, player_white, sgf_content, source_path, source "
                                 "FROM kifu_albums WHERE id=7")).one() == (
            "吴清源", "木谷实", "(;FF[4]PB[吴清源]SO[CWI])", "archive/7.sgf", "SO value"
        )
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("UPDATE kifu_albums SET black_player_id=999 WHERE id=7"))


def test_kifu_catalog_tables_are_protected_and_unconstrained_sqlite_columns_fail_closed(engine):
    assert {"kifu_albums", "kifu_players", "kifu_events", "kifu_player_aliases", "kifu_event_aliases",
            "kifu_player_names", "kifu_event_names", "kifu_sources", "kifu_album_sources",
            "kifu_dedup_batches", "kifu_dedup_changes"} <= migrations.PROTECTED_TABLES
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE kifu_albums (id INTEGER PRIMARY KEY, black_player_id INTEGER)"))
    with pytest.raises(RuntimeError, match="black_player_id"):
        migrations.migrate_kifu_catalog_schema(engine)


def test_postgres_migration_adds_real_foreign_keys_to_legacy_columns():
    statements = migrations.postgres_kifu_album_fk_statements(existing_columns=set(), existing_fks={})
    ddl = "\n".join(statements)
    assert 'ADD COLUMN IF NOT EXISTS "black_player_id" INTEGER' in ddl
    assert 'FOREIGN KEY ("black_player_id") REFERENCES "kifu_players" (id) NOT VALID' in ddl
    assert 'FOREIGN KEY ("duplicate_of_id") REFERENCES "kifu_albums" (id) NOT VALID' in ddl
    assert ddl.count("NOT VALID") == 4


def test_postgres_album_indexes_are_planned_concurrently_and_wrong_indexes_fail():
    statements = migrations.postgres_kifu_album_index_statements(existing_indexes={})
    assert len(statements) == 4
    assert all(statement.startswith("CREATE INDEX CONCURRENTLY") for statement in statements)
    assert any("ix_kifu_albums_black_player_id" in statement for statement in statements)
    valid = ("kifu_albums", ("black_player_id",), True, True)
    assert len(migrations.postgres_kifu_album_index_statements(
        existing_indexes={"ix_kifu_albums_black_player_id": valid}
    )) == 3
    with pytest.raises(RuntimeError, match="ix_kifu_albums_black_player_id"):
        migrations.postgres_kifu_album_index_statements(
            existing_indexes={"ix_kifu_albums_black_player_id": ("kifu_albums", ("black_player_id",), False, True)}
        )
    for wrong in [
        ("other_table", ("black_player_id",), True, True),
        ("kifu_albums", ("white_player_id",), True, True),
        ("kifu_albums", ("black_player_id", "white_player_id"), True, True),
        ("kifu_albums", ("black_player_id",), True, False),
    ]:
        with pytest.raises(RuntimeError, match="ix_kifu_albums_black_player_id"):
            migrations.postgres_kifu_album_index_statements(
                existing_indexes={"ix_kifu_albums_black_player_id": wrong}
            )


def test_startup_checks_indexes_without_building_them(engine, monkeypatch):
    monkeypatch.setattr(migrations, "create_kifu_album_identity_indexes", lambda _engine: pytest.fail("startup build"))
    models_db.Base.metadata.create_all(engine)
    SQLAlchemyUserRepository(sessionmaker(bind=engine)).init_db()


def test_postgres_index_status_query_uses_resolved_album_oid():
    query = migrations.POSTGRES_KIFU_ALBUM_INDEX_STATUS_SQL
    assert "pg_index.indrelid = to_regclass('kifu_albums')" in query
    assert "current_schema()" not in query


def test_postgres_fk_validation_is_explicit_and_only_for_unvalidated_constraints():
    fk_statuses = {
        "black_player_id": ("fk_kifu_albums_black_player_id", False),
        "white_player_id": ("fk_kifu_albums_white_player_id", True),
        "event_id": ("fk_kifu_albums_event_id", True),
        "duplicate_of_id": ("fk_kifu_albums_duplicate_of_id", True),
    }
    assert migrations.postgres_kifu_album_validation_statements(fk_statuses) == [
        'ALTER TABLE "kifu_albums" VALIDATE CONSTRAINT "fk_kifu_albums_black_player_id"'
    ]


def test_migration_rejects_fk_to_non_id_target(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE kifu_albums "
                          "(id INTEGER PRIMARY KEY, black_player_id INTEGER REFERENCES kifu_players(canonical_name))"))
    with pytest.raises(RuntimeError, match="black_player_id"):
        migrations.migrate_kifu_catalog_schema(engine)
