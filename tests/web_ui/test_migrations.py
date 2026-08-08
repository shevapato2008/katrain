"""Phase 2: lightweight non-destructive migration.

Simulates an existing DB whose `users` table predates the billing columns, then
asserts add_missing_columns/create_missing_indexes bring it up to date WITHOUT
dropping data, and that billing tables are protected.
"""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from katrain.web.core import migrations, models_db
from katrain.web.core.ai_ladder_ranked import AiLadderOpponentSnapshot, AiLadderRankedRepository


@pytest.fixture
def legacy_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # Old-style users table: no is_admin, credits as float — and a real row.
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, uuid TEXT, username TEXT, "
                "hashed_password TEXT, rank TEXT, net_wins INTEGER, elo_points INTEGER, "
                "credits FLOAT, avatar_url TEXT, created_at TEXT, updated_at TEXT)"
            )
        )
        conn.execute(text("INSERT INTO users (id, username, hashed_password, credits) VALUES (1, 'old', 'h', 42)"))
    return engine


def test_add_missing_columns_preserves_data(legacy_engine):
    # New tables (billing) get created by create_all; existing users table is ALTERed.
    models_db.Base.metadata.create_all(bind=legacy_engine)
    migrations.add_missing_columns(legacy_engine)

    cols = {c["name"] for c in inspect(legacy_engine).get_columns("users")}
    assert "is_admin" in cols

    with legacy_engine.connect() as conn:
        row = conn.execute(text("SELECT username, credits, is_admin FROM users WHERE id=1")).first()
    assert row[0] == "old"  # data preserved
    assert int(row[1]) == 42
    assert row[2] in (0, False, None)  # default-ish, not crashing


def test_create_missing_indexes(legacy_engine):
    models_db.Base.metadata.create_all(bind=legacy_engine)
    migrations.add_missing_columns(legacy_engine)
    migrations.create_missing_indexes(legacy_engine)
    # billing ledger composite index should exist
    idx = {ix["name"] for ix in inspect(legacy_engine).get_indexes("credit_transactions")}
    assert "ix_credit_tx_user_status" in idx


def test_asset_tables_are_protected_from_the_drift_rebuild():
    """Tables the SQLite drift fallback must never drop and recreate.

    Credits are money. The ai_ladder tables are the sole derivation of every
    user's 段位 -- profile, decision ledger, the in-flight game, and the retained
    legacy ledger -- so rebuilding any of them would silently reset the ladder.
    """
    assert {
        "credit_transactions",
        "redeem_codes",
        "recharge_orders",
        "ai_ladder_profiles",
        "ai_ladder_game_ledger",
        "ai_ladder_pending_games",
        "ai_ladder_active_games",
        "ai_ladder_game_ledger_legacy_v1",
    } == migrations.PROTECTED_TABLES
    # Billing is a strict subset: the drift rebuild must refuse both groups.
    assert migrations.BILLING_TABLES < migrations.PROTECTED_TABLES


def test_ai_ladder_active_game_schema_and_terminal_origin_columns_are_added_without_data_loss():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, hashed_password TEXT)"))
        conn.execute(text("INSERT INTO users VALUES (1, 'legacy-user', 'hash')"))
        conn.execute(
            text(
                "CREATE TABLE ai_ladder_pending_games ("
                "game_id VARCHAR(32) PRIMARY KEY, user_id INTEGER NOT NULL UNIQUE, session_id VARCHAR(64) NOT NULL UNIQUE, "
                "user_color VARCHAR(1) NOT NULL, game_type VARCHAR(32) NOT NULL, opponent_rung INTEGER NOT NULL, "
                "opponent_rank_name VARCHAR(64) NOT NULL, opponent_config_snapshot JSON NOT NULL, "
                "opponent_certification_status VARCHAR(16) NOT NULL, opponent_availability VARCHAR(16) NOT NULL, "
                "opponent_route VARCHAR(16) NOT NULL, ai_subtype VARCHAR(32) NOT NULL, execution_identity VARCHAR(64) NOT NULL, "
                "game_saved BOOLEAN NOT NULL, saved_result VARCHAR(50), created_at DATETIME, updated_at DATETIME)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO ai_ladder_pending_games VALUES ("
                "'legacy-pending', 1, 'legacy-session', 'B', 'ai_ladder_ranked', 20, '1级', '{}', "
                "'certified', 'available', 'server', 'ai:ladder', 'identity', FALSE, NULL, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE ai_ladder_game_ledger ("
                "id INTEGER PRIMARY KEY, game_id VARCHAR(64) NOT NULL UNIQUE, user_id INTEGER NOT NULL, "
                "user_color VARCHAR(1) NOT NULL, result VARCHAR(16) NOT NULL, game_type VARCHAR(32) NOT NULL, "
                "opponent_rung INTEGER, opponent_rank_name VARCHAR(64), opponent_config_snapshot JSON, "
                "opponent_certification_status VARCHAR(16), opponent_availability VARCHAR(16), opponent_route VARCHAR(16), "
                "counted BOOLEAN NOT NULL, reason VARCHAR(32), settled_at DATETIME NOT NULL)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO ai_ladder_game_ledger VALUES ("
                "1, 'legacy-settled', 1, 'W', 'loss', 'ai_ladder_ranked', 20, '1级', '{}', "
                "'certified', 'available', 'server', TRUE, NULL, CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE user_games (id VARCHAR(32) PRIMARY KEY, user_id INTEGER NOT NULL, "
                "source VARCHAR(50) NOT NULL, sgf_content TEXT)"
            )
        )
        conn.execute(text("INSERT INTO user_games VALUES ('legacy-game', 1, 'play_ai', '(;FF[4])')"))

    models_db.Base.metadata.create_all(bind=engine)
    migrations.add_missing_columns(engine)

    inspector = inspect(engine)
    assert "ai_ladder_active_games" in inspector.get_table_names()
    active_columns = {column["name"] for column in inspector.get_columns("ai_ladder_active_games")}
    assert {
        "game_id",
        "user_id",
        "origin_device_id",
        "origin_session_id",
        "state",
        "version",
        "reservation_key_hash",
        "rules_snapshot",
        "time_control_snapshot",
    } <= active_columns
    assert "reservation_key" in {column["name"] for column in inspector.get_columns("ai_ladder_pending_games")}
    assert {
        "origin_device_id",
        "deciding_device_id",
        "terminal_source",
        "decided_at",
    } <= {column["name"] for column in inspector.get_columns("ai_ladder_game_ledger")}
    assert "origin_device_id" in {column["name"] for column in inspector.get_columns("user_games")}

    with engine.connect() as conn:
        assert conn.execute(text("SELECT game_id, reservation_key FROM ai_ladder_pending_games")).one() == (
            "legacy-pending",
            None,
        )
        assert conn.execute(
            text("SELECT game_id, origin_device_id, deciding_device_id, terminal_source, decided_at "
                 "FROM ai_ladder_game_ledger")
        ).one() == ("legacy-settled", None, None, None, None)
        assert conn.execute(text("SELECT id, origin_device_id FROM user_games")).one() == ("legacy-game", None)

    # Every step remains safe to re-run and keeps the legacy rows intact.
    models_db.Base.metadata.create_all(bind=engine)
    migrations.add_missing_columns(engine)
    assert any(
        constraint["column_names"] == ["user_id"]
        for constraint in inspect(engine).get_unique_constraints("ai_ladder_active_games")
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    common = dict(
        origin_device_id="board-a",
        state="active",
        version=0,
        reservation_key_hash="a" * 64,
        user_color="B",
        game_type="ai_ladder_ranked",
        opponent_rung=20,
        opponent_rank_name="1级",
        opponent_config_snapshot={},
        opponent_certification_status="certified",
        opponent_availability="available",
        opponent_route="server",
        ai_subtype="ai:ladder",
        execution_identity="identity",
        rules_snapshot={},
        time_control_snapshot={},
    )
    with sessions() as db:
        db.add(models_db.AiLadderActiveGame(game_id="active-one", user_id=1, **common))
        db.commit()
        db.add(models_db.AiLadderActiveGame(game_id="active-two", user_id=1, **common))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM ai_ladder_pending_games")).scalar_one() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM ai_ladder_game_ledger")).scalar_one() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM user_games")).scalar_one() == 1


def test_terminal_audit_fields_are_all_legacy_null_or_a_complete_valid_provenance_tuple():
    engine = create_engine("sqlite:///:memory:")
    models_db.Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, username, hashed_password, credits, is_admin) "
                "VALUES (1, 'audit-owner', 'x', 10000, FALSE)"
            )
        )
        base = (
            "INSERT INTO ai_ladder_game_ledger "
            "(game_id, user_id, user_color, result, game_type, counted, reason, settled_at, "
            "origin_device_id, deciding_device_id, terminal_source, decided_at) VALUES "
        )
        conn.execute(
            text(base + "('legacy-null', 1, 'B', 'loss', 'pvp', FALSE, 'invalid_game_type', CURRENT_TIMESTAMP, "
                 "NULL, NULL, NULL, NULL)")
        )
        conn.execute(
            text(base + "('complete-audit', 1, 'B', 'loss', 'pvp', FALSE, 'invalid_game_type', CURRENT_TIMESTAMP, "
                 "'origin', 'decider', 'remote_resign', CURRENT_TIMESTAMP)")
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(base + "('partial-audit', 1, 'B', 'loss', 'pvp', FALSE, 'invalid_game_type', CURRENT_TIMESTAMP, "
                     "'origin', NULL, 'remote_resign', CURRENT_TIMESTAMP)")
            )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(base + "('bad-source', 1, 'B', 'loss', 'pvp', FALSE, 'invalid_game_type', CURRENT_TIMESTAMP, "
                     "'origin', 'decider', 'client_claim', CURRENT_TIMESTAMP)")
            )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(base + "('missing-source', 1, 'B', 'loss', 'pvp', FALSE, 'invalid_game_type', CURRENT_TIMESTAMP, "
                     "'origin', 'decider', NULL, CURRENT_TIMESTAMP)")
            )


def test_sqlite_terminal_audit_triggers_upgrade_legacy_table_without_rebuilding_and_are_idempotent():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE ai_ladder_game_ledger (id INTEGER PRIMARY KEY, game_id VARCHAR(64) UNIQUE, "
                "origin_device_id VARCHAR(64), deciding_device_id VARCHAR(64), terminal_source VARCHAR(32), "
                "decided_at DATETIME)"
            )
        )
        conn.execute(text("INSERT INTO ai_ladder_game_ledger (id, game_id) VALUES (7, 'legacy-preserved')"))

    migrations.enforce_ai_ladder_terminal_audit_schema(engine)
    migrations.enforce_ai_ladder_terminal_audit_schema(engine)

    with engine.connect() as conn:
        assert conn.execute(text("SELECT id, game_id FROM ai_ladder_game_ledger")).one() == (7, "legacy-preserved")
        triggers = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='ai_ladder_game_ledger'")
            )
        }
        assert triggers == {
            "trg_ai_ladder_ledger_terminal_audit_insert",
            "trg_ai_ladder_ledger_terminal_audit_update",
        }
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO ai_ladder_game_ledger "
                    "(id, game_id, origin_device_id, terminal_source) "
                    "VALUES (8, 'partial', 'origin', 'played_result')"
                )
            )


def test_postgres_terminal_audit_constraint_is_non_destructive_and_idempotent():
    statements = migrations.postgres_ai_ladder_terminal_audit_statements(existing_checks=set())
    sql = "\n".join(statements)
    assert "ADD CONSTRAINT ck_ai_ladder_ledger_terminal_audit" in sql
    assert "played_result" in sql and "remote_resign" in sql and "recovery" in sql
    assert "DROP TABLE" not in sql and "DELETE" not in sql
    assert migrations.postgres_ai_ladder_terminal_audit_statements(
        existing_checks={"ck_ai_ladder_ledger_terminal_audit"}
    ) == []


def test_pending_ai_ladder_table_is_protected_and_has_one_pending_per_user_constraint():
    engine = create_engine("sqlite:///:memory:")
    models_db.Base.metadata.create_all(bind=engine)

    assert "ai_ladder_pending_games" in migrations.AI_LADDER_TABLES
    uniques = inspect(engine).get_unique_constraints("ai_ladder_pending_games")
    assert any(constraint["column_names"] == ["user_id"] for constraint in uniques)


def test_pending_ai_ladder_unique_violation_rolls_back_without_losing_existing_row():
    engine = create_engine("sqlite:///:memory:")
    models_db.Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        db.add(models_db.User(id=1, username="pending-owner", hashed_password="x", rank="20k"))
        db.add(
            models_db.AiLadderPendingGame(
                game_id="a" * 32,
                user_id=1,
                session_id="session-a",
                user_color="B",
                game_type="ai_ladder_ranked",
                opponent_rung=16,
                opponent_rank_name="5级",
                opponent_config_snapshot={"config_digest": "d", "config_version": "v"},
                opponent_certification_status="certified",
                opponent_availability="available",
                opponent_route="server",
                ai_subtype="ai:ladder",
                execution_identity="d",
                game_saved=False,
            )
        )
        db.commit()
        db.add(
            models_db.AiLadderPendingGame(
                game_id="b" * 32,
                user_id=1,
                session_id="session-b",
                user_color="B",
                game_type="ai_ladder_ranked",
                opponent_rung=16,
                opponent_rank_name="5级",
                opponent_config_snapshot={"config_digest": "d", "config_version": "v"},
                opponent_certification_status="certified",
                opponent_availability="available",
                opponent_route="server",
                ai_subtype="ai:ladder",
                execution_identity="d",
                game_saved=False,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert [row.game_id for row in db.query(models_db.AiLadderPendingGame).all()] == ["a" * 32]


def test_backfill_ai_ladder_decisions_preserves_old_valid_history(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'old-ai-ladder.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL, hashed_password TEXT NOT NULL, "
                "rank TEXT, net_wins INTEGER, elo_points INTEGER)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE ai_ladder_profiles (user_id INTEGER PRIMARY KEY, ai_ladder_rung INTEGER, "
                "placement_lo INTEGER NOT NULL, placement_hi INTEGER NOT NULL, placement_completed INTEGER NOT NULL, "
                "net_score INTEGER NOT NULL, version INTEGER NOT NULL, created_at DATETIME NOT NULL, "
                "updated_at DATETIME NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE ai_ladder_game_ledger (id INTEGER PRIMARY KEY, game_id VARCHAR(64) UNIQUE NOT NULL, "
                "user_id INTEGER NOT NULL, user_color VARCHAR(1) NOT NULL, result VARCHAR(16) NOT NULL, "
                "game_type VARCHAR(32) NOT NULL, opponent_rung INTEGER NOT NULL, opponent_rank_name VARCHAR(64) NOT NULL, "
                "opponent_config_snapshot JSON NOT NULL, opponent_certification_status VARCHAR(16) NOT NULL, "
                "opponent_availability VARCHAR(16) NOT NULL, opponent_route VARCHAR(16) NOT NULL, "
                "settled_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                "CONSTRAINT ck_ai_ladder_ledger_user_color CHECK (user_color IN ('B', 'W')), "
                "CONSTRAINT ck_ai_ladder_ledger_result CHECK (result IN ('win', 'loss')), "
                "CONSTRAINT ck_ai_ladder_ledger_game_type CHECK (game_type = 'ai_ladder_ranked'), "
                "CONSTRAINT ck_ai_ladder_ledger_opponent_rung CHECK (opponent_rung BETWEEN 1 AND 41), "
                "CONSTRAINT ck_ai_ladder_ledger_certification CHECK "
                "(opponent_certification_status = 'certified'), "
                "CONSTRAINT ck_ai_ladder_ledger_availability CHECK (opponent_availability = 'available'), "
                "CONSTRAINT ck_ai_ladder_ledger_route CHECK (opponent_route IN ('local', 'server')))"
            )
        )
        conn.execute(
            text(
                "INSERT INTO users (id, username, hashed_password, rank, net_wins) VALUES (1, 'old-fan', 'x', '5d', 2)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO ai_ladder_profiles "
                "(user_id, ai_ladder_rung, placement_lo, placement_hi, placement_completed, net_score, version, "
                "created_at, updated_at) VALUES (1, 20, 20, 20, 5, 1, 1, "
                "'2026-08-03 12:00:00', '2026-08-03 12:00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO ai_ladder_game_ledger "
                "(id, game_id, user_id, user_color, result, game_type, opponent_rung, opponent_rank_name, "
                "opponent_config_snapshot, opponent_certification_status, opponent_availability, opponent_route) "
                "VALUES (1, 'old-valid-game', 1, 'B', 'win', 'ai_ladder_ranked', 20, '1级', "
                '\'{"config_digest":"old-digest","config_version":"old-v1"}\', '
                "'certified', 'available', 'server')"
            )
        )

    migrations.migrate_ai_ladder_decision_schema(engine)
    migrations.add_missing_columns(engine)
    migrations.backfill_ai_ladder_decisions(engine)
    migrations.create_missing_indexes(engine)

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT counted, reason FROM ai_ladder_game_ledger WHERE game_id='old-valid-game'")
        ).one()
        assert row[0] in (1, True)
        assert row[1] is None

    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    repo = AiLadderRankedRepository(sessions)
    replay = repo.settle_game(
        user_id=1,
        game_id="old-valid-game",
        user_color="B",
        result="loss",
        game_type="ai_ladder_ranked",
        opponent=AiLadderOpponentSnapshot(
            rung=20,
            rank_name="1级",
            config_snapshot={"config_digest": "new-digest", "config_version": "new-v1"},
            certification_status="certified",
            availability="available",
            route="server",
        ),
    )
    assert (replay.counted, replay.replayed, replay.net_score) == (True, True, 1)
    assert repo.recent_counted_results(1) == ["win"]

    excluded = [
        repo.settle_game(
            user_id=1,
            game_id="old-pvp",
            user_color="B",
            result="win",
            game_type="pvp",
            opponent=None,
        ),
        repo.settle_game(
            user_id=1,
            game_id="old-inconclusive",
            user_color="B",
            result="inconclusive",
            game_type="ai_ladder_ranked",
            opponent=AiLadderOpponentSnapshot(
                rung=20,
                rank_name="1级",
                config_snapshot={"config_digest": "digest", "config_version": "v1"},
                certification_status="certified",
                availability="available",
                route="server",
            ),
        ),
        repo.settle_game(
            user_id=1,
            game_id="old-unavailable",
            user_color="B",
            result="loss",
            game_type="ai_ladder_ranked",
            opponent=AiLadderOpponentSnapshot(
                rung=20,
                rank_name="1级",
                config_snapshot={"config_digest": "digest", "config_version": "v1"},
                certification_status="certified",
                availability="unavailable",
                route="server",
            ),
        ),
    ]
    assert [decision.counted for decision in excluded] == [False, False, False]
    assert [decision.reason for decision in excluded] == [
        "invalid_game_type",
        "inconclusive",
        "opponent_not_eligible",
    ]

    with sessions() as session:
        profile = session.get(models_db.AiLadderProfile, 1)
        assert (profile.ai_ladder_rung, profile.net_score, profile.version) == (20, 1, 1)
        assert session.query(models_db.AiLadderGameLedger).count() == 4

    migrations.migrate_ai_ladder_decision_schema(engine)
    migrations.add_missing_columns(engine)
    migrations.backfill_ai_ladder_decisions(engine)
    migrations.create_missing_indexes(engine)

    inspector = inspect(engine)
    assert migrations.AI_LADDER_LEGACY_TABLE in inspector.get_table_names()
    with engine.connect() as conn:
        assert conn.execute(text(f"SELECT COUNT(*) FROM {migrations.AI_LADDER_LEGACY_TABLE}")).scalar_one() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM ai_ladder_game_ledger")).scalar_one() == 4


def test_postgres_ai_ladder_migration_ddl_is_non_destructive():
    statements = migrations.postgres_ai_ladder_decision_statements(
        existing_columns={
            "id",
            "game_id",
            "user_id",
            "user_color",
            "result",
            "game_type",
            "opponent_rung",
            "opponent_rank_name",
            "opponent_config_snapshot",
            "opponent_certification_status",
            "opponent_availability",
            "opponent_route",
            "settled_at",
        },
        existing_checks={
            "ck_ai_ladder_ledger_result",
            "ck_ai_ladder_ledger_game_type",
            "ck_ai_ladder_ledger_opponent_rung",
            "ck_ai_ladder_ledger_certification",
            "ck_ai_ladder_ledger_availability",
            "ck_ai_ladder_ledger_route",
        },
    )
    sql = "\n".join(statements)
    assert "ADD COLUMN IF NOT EXISTS counted BOOLEAN" in sql
    assert "ADD COLUMN IF NOT EXISTS reason VARCHAR(32)" in sql
    assert "SET counted = TRUE" in sql
    assert "counted = FALSE AND reason IS NULL" in sql
    assert "counted IS NULL OR (counted = FALSE AND reason IS NULL)" in sql
    assert "ALTER COLUMN opponent_rung DROP NOT NULL" in sql
    assert "DROP CONSTRAINT IF EXISTS ck_ai_ladder_ledger_result" in sql
    assert "ADD CONSTRAINT ck_ai_ladder_ledger_decision" in sql
    assert "DROP TABLE" not in sql
    assert "DELETE" not in sql


def test_ai_ladder_migration_fails_closed_when_backup_history_is_missing():
    engine = create_engine("sqlite:///:memory:")
    models_db.Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                f'CREATE TABLE "{migrations.AI_LADDER_LEGACY_TABLE}" AS ' "SELECT * FROM ai_ladder_game_ledger WHERE 0"
            )
        )
        conn.execute(
            text(
                f'INSERT INTO "{migrations.AI_LADDER_LEGACY_TABLE}" '
                "(id, game_id, user_id, user_color, result, game_type, opponent_rung, opponent_rank_name, "
                "opponent_config_snapshot, opponent_certification_status, opponent_availability, opponent_route, "
                "counted, reason, settled_at) VALUES "
                "(1, 'missing-history', 1, 'B', 'win', 'ai_ladder_ranked', 1, '20级', "
                '\'{"config_digest":"d","config_version":"v"}\', '
                "'certified', 'available', 'server', TRUE, NULL, CURRENT_TIMESTAMP)"
            )
        )

    with pytest.raises(RuntimeError, match="legacy decision.*missing"):
        migrations.migrate_ai_ladder_decision_schema(engine)


def test_ai_ladder_migration_fails_closed_when_only_backup_exists():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text(f'CREATE TABLE "{migrations.AI_LADDER_LEGACY_TABLE}" (game_id VARCHAR(64))'))

    with pytest.raises(RuntimeError, match="backup exists without final"):
        migrations.migrate_ai_ladder_decision_schema(engine)


@pytest.mark.parametrize(
    "tamper_sql",
    [
        "UPDATE ai_ladder_game_ledger SET opponent_rank_name = 'tampered' WHERE game_id = 'legacy-game'",
        "UPDATE ai_ladder_game_ledger SET counted = FALSE, reason = 'tampered' WHERE game_id = 'legacy-game'",
    ],
)
def test_ai_ladder_migration_fails_closed_when_backup_history_differs(tamper_sql):
    engine = create_engine("sqlite:///:memory:")
    models_db.Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ai_ladder_game_ledger "
                "(id, game_id, user_id, user_color, result, game_type, opponent_rung, opponent_rank_name, "
                "opponent_config_snapshot, opponent_certification_status, opponent_availability, opponent_route, "
                "counted, reason, settled_at) VALUES "
                "(1, 'legacy-game', 1, 'B', 'win', 'ai_ladder_ranked', 1, '20级', "
                '\'{"config_digest":"d","config_version":"v"}\', '
                "'certified', 'available', 'server', TRUE, NULL, CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(f'CREATE TABLE "{migrations.AI_LADDER_LEGACY_TABLE}" AS ' "SELECT * FROM ai_ladder_game_ledger")
        )
        conn.execute(text(tamper_sql))

    with pytest.raises(RuntimeError, match="legacy decision.*inconsistent"):
        migrations.migrate_ai_ladder_decision_schema(engine)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
