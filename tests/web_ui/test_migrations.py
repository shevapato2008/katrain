"""Phase 2: lightweight non-destructive migration.

Simulates an existing DB whose `users` table predates the billing columns, then
asserts add_missing_columns/create_missing_indexes bring it up to date WITHOUT
dropping data, and that billing tables are protected.
"""

import pytest
from sqlalchemy import create_engine, inspect, text

from katrain.web.core import migrations, models_db


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
