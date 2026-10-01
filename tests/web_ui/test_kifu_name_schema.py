"""Name evidence schema keeps raw catalog data and legacy decisions intact."""

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from katrain.web.core import migrations, models_db
from katrain.web.core.auth import SQLAlchemyUserRepository
from katrain.web.kifu import migrate_catalog

NEW_TABLES = {
    "kifu_raw_player_values",
    "kifu_raw_event_values",
    "kifu_raw_player_names",
    "kifu_raw_event_names",
    "kifu_name_source_registry",
    "kifu_name_research_evidence",
    "kifu_name_batches",
    "kifu_name_changes",
}


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def _legacy_name_tables(engine):
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE kifu_player_names (id INTEGER PRIMARY KEY, player_id INTEGER NOT NULL "
                "REFERENCES kifu_players(id), lang VARCHAR(2) NOT NULL, display_name VARCHAR(512) NOT NULL, "
                "status VARCHAR(16) NOT NULL, reference_url TEXT, reference_kind VARCHAR(32), "
                "verified_at DATETIME, created_at DATETIME, UNIQUE(player_id, lang))"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE kifu_event_names (id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL "
                "REFERENCES kifu_events(id), lang VARCHAR(2) NOT NULL, display_name VARCHAR(256) NOT NULL, "
                "status VARCHAR(16) NOT NULL, reference_url TEXT, reference_kind VARCHAR(32), "
                "verified_at DATETIME, created_at DATETIME, UNIQUE(event_id, lang))"
            )
        )
    models_db.Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO kifu_players (id, canonical_name) VALUES (1, '吴清源')"))
        conn.execute(text("INSERT INTO kifu_events (id, canonical_name) VALUES (2, '大手合')"))
        conn.execute(
            text(
                "INSERT INTO kifu_player_names (id, player_id, lang, display_name, status, reference_url) "
                "VALUES (3, 1, 'en', 'Go Seigen', 'verified', 'legacy-source')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO kifu_event_names (id, event_id, lang, display_name, status) "
                "VALUES (4, 2, 'en', 'Oteai', 'verified')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO kifu_albums "
                "(id, player_black, player_white, event, sgf_content, source_path) "
                "VALUES (5, '吴清源 九段', '木谷实', '大手合 第3局', "
                "'(;FF[4]PB[吴清源 九段]PW[木谷实]EV[大手合 第3局])', 'old.sgf')"
            )
        )


def test_empty_db_creates_all_name_tables_and_real_constraints(engine):
    SQLAlchemyUserRepository(sessionmaker(bind=engine)).init_db()
    assert NEW_TABLES <= set(inspect(engine).get_table_names())
    for table, owner in (("kifu_raw_player_values", "raw_value"), ("kifu_raw_event_values", "raw_value")):
        assert owner in {column["name"] for column in inspect(engine).get_columns(table)}
    evidence_fks = {fk["referred_table"] for fk in inspect(engine).get_foreign_keys("kifu_name_research_evidence")}
    assert {
        "kifu_players",
        "kifu_events",
        "kifu_raw_player_values",
        "kifu_raw_event_values",
        "kifu_name_source_registry",
    } <= evidence_fks
    assert {fk["referred_table"] for fk in inspect(engine).get_foreign_keys("kifu_player_names")} >= {
        "kifu_players",
        "kifu_name_research_evidence",
    }

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO kifu_players (id, canonical_name) VALUES (1, '吴清源')"))
        conn.execute(text("INSERT INTO kifu_events (id, canonical_name) VALUES (2, '大手合')"))
        conn.execute(
            text(
                "INSERT INTO kifu_raw_player_values "
                "(id, raw_value, category, review_status) VALUES (1, '吴清源 九段', 'person_rank', 'pending')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO kifu_name_source_registry " "(id, version, sha256, registry) VALUES (1, 'v1', 'sha', '{}')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO kifu_raw_player_names (raw_player_id, lang, display_name, status) "
                "VALUES (1, 'en', 'Go Seigen', 'review')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO kifu_name_research_evidence "
                "(player_id, lang, revision, source_registry_id, candidate_name, decision_kind, "
                "generation_rule_version, research_payload, producer_id, review_status) "
                "VALUES (1, 'en', 1, 1, 'Go Seigen', 'source', 'r1', '{}', 'producer', 'pending')"
            )
        )
    for sql in (
        "INSERT INTO kifu_raw_player_values (raw_value, category, review_status) "
        "VALUES ('吴清源 九段', 'person_rank', 'pending')",
        "INSERT INTO kifu_raw_player_names (raw_player_id, lang, display_name, status) "
        "VALUES (99, 'en', 'Go Seigen', 'review')",
        "INSERT INTO kifu_raw_player_names (raw_player_id, lang, display_name, status) "
        "VALUES (1, 'en', 'duplicate', 'review')",
        "INSERT INTO kifu_name_research_evidence "
        "(player_id, event_id, lang, revision, source_registry_id, candidate_name, decision_kind, "
        "generation_rule_version, research_payload, producer_id, reviewer_id, review_status) "
        "VALUES (1, 2, 'en', 1, 1, 'x', 'source', 'r1', '{}', 'p', 'r', 'pending')",
        "INSERT INTO kifu_name_research_evidence "
        "(player_id, lang, revision, source_registry_id, candidate_name, decision_kind, "
        "generation_rule_version, research_payload, producer_id, review_status) "
        "VALUES (1, 'en', 1, 1, 'duplicate', 'source', 'r1', '{}', 'producer', 'pending')",
    ):
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text(sql))


def test_legacy_sqlite_name_migration_is_lossless_idempotent_and_unapproved(engine):
    _legacy_name_tables(engine)
    with engine.connect() as conn:
        before = conn.execute(
            text("SELECT player_black, player_white, event, sgf_content " "FROM kifu_albums WHERE id=5")
        ).one()
    migrations.migrate_kifu_name_schema(engine)
    migrations.migrate_kifu_name_schema(engine)
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT player_black, player_white, event, sgf_content " "FROM kifu_albums WHERE id=5")
            ).one()
            == before
        )
        assert conn.execute(
            text(
                "SELECT display_name, status, reference_url, decision_kind, "
                "generation_rule_version, revision, evidence_id "
                "FROM kifu_player_names WHERE id=3"
            )
        ).one() == ("Go Seigen", "verified", "legacy-source", None, None, None, None)
        assert conn.execute(
            text("SELECT display_name, status, evidence_id " "FROM kifu_event_names WHERE id=4")
        ).one() == ("Oteai", "verified", None)
    fks = inspect(engine).get_foreign_keys("kifu_player_names")
    assert any(
        fk["constrained_columns"] == ["evidence_id"] and fk["referred_table"] == "kifu_name_research_evidence"
        for fk in fks
    )
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("UPDATE kifu_player_names SET evidence_id=999 WHERE id=3"))


def test_legacy_sqlite_bare_evidence_column_fails_closed(engine):
    _legacy_name_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE kifu_player_names ADD COLUMN evidence_id INTEGER"))
    with pytest.raises(RuntimeError, match="evidence_id"):
        migrations.migrate_kifu_name_schema(engine)


def test_startup_requires_explicit_migration_for_legacy_name_tables(engine):
    _legacy_name_tables(engine)
    with pytest.raises(RuntimeError, match="migrate_catalog"):
        SQLAlchemyUserRepository(sessionmaker(bind=engine)).init_db()
    assert "decision_kind" not in {column["name"] for column in inspect(engine).get_columns("kifu_player_names")}


def test_startup_rejects_drift_in_new_authoritative_name_table(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE kifu_raw_player_values (id INTEGER PRIMARY KEY)"))
    with pytest.raises(RuntimeError, match="kifu_raw_player_values.*migrate_catalog"):
        SQLAlchemyUserRepository(sessionmaker(bind=engine)).init_db()
    assert {column["name"] for column in inspect(engine).get_columns("kifu_raw_player_values")} == {"id"}


def test_startup_rejects_bare_raw_name_owner_fk(engine):
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE kifu_raw_player_names "
                "(id INTEGER PRIMARY KEY, raw_player_id INTEGER NOT NULL, lang VARCHAR(2) NOT NULL, "
                "display_name TEXT NOT NULL, status VARCHAR(16) NOT NULL, decision_kind VARCHAR(32), "
                "generation_rule_version VARCHAR(64), revision INTEGER, "
                "evidence_id INTEGER REFERENCES kifu_name_research_evidence(id), created_at DATETIME)"
            )
        )
    with pytest.raises(RuntimeError, match="raw_player_id.*foreign key"):
        SQLAlchemyUserRepository(sessionmaker(bind=engine)).init_db()


def test_startup_rejects_missing_registry_unique_constraint(engine):
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE kifu_name_source_registry (id INTEGER PRIMARY KEY, "
                "version VARCHAR(64) NOT NULL, sha256 VARCHAR(64) NOT NULL, registry JSON NOT NULL, "
                "created_at DATETIME)"
            )
        )
    with pytest.raises(RuntimeError, match="kifu_name_source_registry.*unique"):
        SQLAlchemyUserRepository(sessionmaker(bind=engine)).init_db()


def test_explicit_cli_does_not_claim_malformed_name_schema_ready(engine, monkeypatch):
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE kifu_name_source_registry (id INTEGER PRIMARY KEY, "
                "version VARCHAR(64) NOT NULL, sha256 VARCHAR(64) NOT NULL, registry JSON NOT NULL, "
                "created_at DATETIME)"
            )
        )
    monkeypatch.setattr(migrate_catalog, "engine", engine)
    monkeypatch.setattr("sys.argv", ["migrate_catalog", "--validate"])
    with pytest.raises(RuntimeError, match="kifu_name_source_registry.*unique"):
        migrate_catalog.main()


def test_postgres_name_migration_is_non_destructive_and_defers_validation():
    statements = migrations.postgres_kifu_name_statements(
        table="kifu_player_names",
        existing_columns={"id", "player_id", "lang", "display_name", "status"},
        existing_fks={"player_id": {"name": "old", "referred_table": "kifu_players", "referred_columns": ["id"]}},
    )
    sql = "\n".join(statements)
    assert 'ADD COLUMN IF NOT EXISTS "decision_kind"' in sql
    assert 'ADD COLUMN IF NOT EXISTS "evidence_id"' in sql
    assert 'REFERENCES "kifu_name_research_evidence" (id) NOT VALID' in sql
    assert "DROP TABLE" not in sql and "DELETE" not in sql and "UPDATE" not in sql
    assert migrations.postgres_kifu_name_validation_statements(
        {
            "kifu_player_names": ("fk_kifu_player_names_evidence_id", False),
            "kifu_event_names": ("fk_kifu_event_names_evidence_id", True),
        }
    ) == ['ALTER TABLE "kifu_player_names" VALIDATE CONSTRAINT "fk_kifu_player_names_evidence_id"']


def test_name_change_history_is_immutable_after_insert(engine):
    SQLAlchemyUserRepository(sessionmaker(bind=engine)).init_db()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO kifu_name_source_registry (id, version, sha256, registry) " "VALUES (1, 'v1', 'sha', '{}')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO kifu_name_batches "
                "(id, bundle_sha256, inventory_sha256, source_registry_id, reviewed_artifact) "
                "VALUES (1, 'bundle', 'inventory', 1, '{}')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO kifu_name_changes "
                "(id, batch_id, sequence, target_table, target_row_id, before_image, after_image) "
                "VALUES (1, 1, 1, 'kifu_player_names', 7, '{}', '{\"display_name\":\"Go Seigen\"}')"
            )
        )
    for sql in ("UPDATE kifu_name_changes SET target_row_id=8 WHERE id=1", "DELETE FROM kifu_name_changes WHERE id=1"):
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text(sql))


def test_evidence_approval_requires_independent_reviewer(engine):
    SQLAlchemyUserRepository(sessionmaker(bind=engine)).init_db()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO kifu_players (id, canonical_name) VALUES (1, '吴清源')"))
        conn.execute(
            text(
                "INSERT INTO kifu_name_source_registry (id, version, sha256, registry) " "VALUES (1, 'v1', 'sha', '{}')"
            )
        )
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO kifu_name_research_evidence "
                    "(player_id, lang, revision, source_registry_id, candidate_name, decision_kind, "
                    "generation_rule_version, research_payload, producer_id, reviewer_id, reviewed_at, "
                    "review_status) VALUES (1, 'en', 1, 1, 'Go Seigen', 'source', 'r1', '{}', "
                    "'same-agent', 'same-agent', CURRENT_TIMESTAMP, 'approved')"
                )
            )
