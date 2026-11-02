"""Membership receipts survive product-content deletion and schema upgrades."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from katrain.web.core import migrations, models_db as m


def test_membership_models_declare_durable_receipts_and_nonnegative_assets():
    assert hasattr(m, "MembershipTerm"), "MembershipTerm is not implemented"
    assert hasattr(m, "BillingOperation"), "BillingOperation is not implemented"
    assert {"users", "report_tasks", "membership_terms", "billing_operations"} <= migrations.PROTECTED_TABLES
    assert {"billing_version", "operation_id", "generation", "model_sha256"} <= set(
        m.ReportTask.__table__.columns.keys()
    )
    assert {"reserved", "starts_at", "ends_at"} <= set(m.QuotaBucket.__table__.columns.keys())
    assert {"membership_revision", "membership_migrated_at"} <= set(m.User.__table__.columns.keys())
    # Receipts are deliberately not foreign-keyed to mutable/deletable tasks or games.
    assert not m.BillingOperation.__table__.c.task_id.foreign_keys
    assert not m.BillingOperation.__table__.c.game_id.foreign_keys


def test_membership_migration_adds_columns_twice_without_changing_old_assets():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, hashed_password TEXT, credits INTEGER)")
        )
        conn.execute(text("INSERT INTO users VALUES (1, 'old', 'x', 3300)"))
        conn.execute(
            text(
                "CREATE TABLE recharge_orders (id INTEGER PRIMARY KEY, out_trade_no TEXT, user_id INTEGER, package_id TEXT, amount_fen INTEGER, credits INTEGER, provider TEXT, status TEXT)"
            )
        )
        conn.execute(text("INSERT INTO recharge_orders VALUES (1,'old-order',1,'p30',3000,3300,'manual','paid')"))
        conn.execute(
            text(
                "CREATE TABLE quota_buckets (id INTEGER PRIMARY KEY, user_id INTEGER, kind TEXT, period_key TEXT, allowance INTEGER, used INTEGER)"
            )
        )
        conn.execute(text("INSERT INTO quota_buckets VALUES (1,1,'free_report','W:2026-W44',1,1)"))
        conn.execute(
            text(
                "CREATE TABLE report_tasks (id INTEGER PRIMARY KEY, user_id INTEGER, user_game_id TEXT, total_moves INTEGER, analyzed_moves INTEGER)"
            )
        )
        conn.execute(text("INSERT INTO report_tasks VALUES (1,1,'deleted-game',250,250)"))
    migrate = getattr(migrations, "migrate_membership_schema", None)
    assert callable(migrate), "Membership migration is not implemented"
    migrate(engine)
    migrate(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT credits,membership_revision FROM users")).one() == (3300, 0)
        assert conn.execute(
            text("SELECT package_id,amount_fen,credits,status,catalog_version FROM recharge_orders")
        ).one() == ("p30", 3000, 3300, "paid", None)
        assert conn.execute(text("SELECT used,reserved FROM quota_buckets")).one() == (1, 0)
        assert conn.execute(
            text("SELECT total_moves,analyzed_moves,billing_version,generation FROM report_tasks")
        ).one() == (250, 250, None, 0)
        with pytest.raises(IntegrityError):
            conn.execute(text("UPDATE quota_buckets SET reserved=-1"))


def test_new_operations_have_user_kind_key_identity_and_bounded_results():
    assert hasattr(m, "BillingOperation"), "BillingOperation is not implemented"
    engine = create_engine("sqlite:///:memory:")
    m.Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(m.User(id=1, username="u", hashed_password="x"))
        session.commit()
        kwargs = dict(
            user_id=1,
            kind="position",
            idempotency_key="same",
            fingerprint="a" * 64,
            source="wallet",
            profile="normal",
            model_sha256="b" * 64,
            units=1,
            status="reserved",
            catalog_version="membership_20261102_v1",
        )
        session.add(m.BillingOperation(**kwargs))
        session.commit()
        session.add(m.BillingOperation(**kwargs))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        row = session.query(m.BillingOperation).one()
        row.result = {"payload": "x" * 65536}
        with pytest.raises(IntegrityError):
            session.commit()
