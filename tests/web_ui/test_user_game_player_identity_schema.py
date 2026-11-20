"""Additive trusted native seat metadata, without guessing or backfilling old history."""

import os

import pytest
from sqlalchemy import create_engine, inspect, text

from katrain.web.core import migrations, models_db
from tests.web_ui.membership_test_support import membership_pg_schema_engine


def _assert_upgrade_twice_preserves_history(engine):
    sgf = "(;SZ[19]PB[original black]PW[original white]C[do not rewrite])"
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE user_games (id VARCHAR(32) PRIMARY KEY, user_id INTEGER, source VARCHAR(50), sgf_content TEXT, sgf_hash VARCHAR(64))"
            )
        )
        conn.execute(text("INSERT INTO user_games VALUES ('legacy', 7, 'play_human', :sgf, 'old-hash')"), {"sgf": sgf})
    migrations.add_missing_columns(engine)
    migrations.add_missing_columns(engine)
    columns = {col["name"]: col for col in inspect(engine).get_columns("user_games")}
    for name in ("player_black_user_id", "player_white_user_id"):
        assert name in models_db.UserGame.__table__.columns
        assert columns[name]["nullable"] and columns[name]["default"] is None
        assert columns[name]["type"]._type_affinity is models_db.UserGame.__table__.c[name].type._type_affinity
    with engine.connect() as conn:
        assert conn.execute(
            text(
                "SELECT id,user_id,source,sgf_content,sgf_hash,player_black_user_id,player_white_user_id FROM user_games"
            )
        ).one() == (
            "legacy",
            7,
            "play_human",
            sgf,
            "old-hash",
            None,
            None,
        )


def test_sqlite_native_player_identity_migration_is_additive_and_idempotent():
    engine = create_engine("sqlite:///:memory:")
    try:
        _assert_upgrade_twice_preserves_history(engine)
    finally:
        engine.dispose()


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Dedicated local PostgreSQL test URL is not configured")
def test_postgres_native_player_identity_migration_is_additive_and_idempotent(membership_pg_schema_engine):
    _assert_upgrade_twice_preserves_history(membership_pg_schema_engine)
