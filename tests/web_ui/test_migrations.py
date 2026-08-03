"""Phase 2: lightweight non-destructive migration.

Simulates an existing DB whose `users` table predates the billing columns, then
asserts add_missing_columns/create_missing_indexes bring it up to date WITHOUT
dropping data, and that billing tables are protected.
"""

import pytest
from sqlalchemy import create_engine, inspect, text
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


def test_billing_tables_are_protected_constant():
    assert {"credit_transactions", "redeem_codes", "recharge_orders"} == migrations.BILLING_TABLES


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
                "settled_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
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

    models_db.Base.metadata.create_all(bind=engine)
    migrations.add_missing_columns(engine)
    migrations.backfill_ai_ladder_decisions(engine)

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
