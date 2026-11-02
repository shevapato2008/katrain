"""Real PostgreSQL upgrade checks, confined to a generated TEST schema."""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from katrain.web.core import billing_environment, migrations
from katrain.web.core.config import Settings
from tests.web_ui.membership_test_support import membership_pg_schema_engine


def test_postgres_membership_upgrade_twice_preserves_old_financial_facts(membership_pg_schema_engine):
    engine = membership_pg_schema_engine
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY,username TEXT,hashed_password TEXT,credits INTEGER)")
        )
        conn.execute(text("INSERT INTO users VALUES (1,'old','x',3300)"))
        conn.execute(
            text(
                "CREATE TABLE recharge_orders (id INTEGER PRIMARY KEY,out_trade_no TEXT,user_id INTEGER,package_id TEXT,amount_fen INTEGER,credits INTEGER,provider TEXT,status TEXT)"
            )
        )
        conn.execute(text("INSERT INTO recharge_orders VALUES (1,'old-order',1,'p30',3000,3300,'manual','paid')"))
        conn.execute(
            text(
                "CREATE TABLE credit_transactions (id INTEGER PRIMARY KEY,user_id INTEGER,delta INTEGER,ref_id TEXT,status TEXT,balance_after INTEGER)"
            )
        )
        conn.execute(text("INSERT INTO credit_transactions VALUES (1,1,3300,'order:old-order','committed',3300)"))
        conn.execute(
            text(
                "CREATE TABLE quota_buckets (id INTEGER PRIMARY KEY,user_id INTEGER,kind TEXT,period_key TEXT,allowance INTEGER,used INTEGER)"
            )
        )
        conn.execute(text("INSERT INTO quota_buckets VALUES (1,1,'free_report','W:2026-W44',1,1)"))
        conn.execute(
            text(
                "CREATE TABLE report_tasks (id INTEGER PRIMARY KEY,user_id INTEGER,user_game_id TEXT,total_moves INTEGER,analyzed_moves INTEGER)"
            )
        )
        conn.execute(text("INSERT INTO report_tasks VALUES (1,1,'old-game',250,250)"))
    for _ in range(2):
        migrations.migrate_membership_schema(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT username,credits,membership_revision FROM users")).one() == ("old", 3300, 0)
        assert conn.execute(
            text("SELECT package_id,amount_fen,credits,status,catalog_version FROM recharge_orders")
        ).one() == ("p30", 3000, 3300, "paid", None)
        assert conn.execute(text("SELECT delta,ref_id,status,balance_after FROM credit_transactions")).one() == (
            3300,
            "order:old-order",
            "committed",
            3300,
        )
        assert conn.execute(text("SELECT used,reserved FROM quota_buckets")).one() == (1, 0)
        assert conn.execute(
            text("SELECT total_moves,analyzed_moves,billing_version,generation,analysis_sgf FROM report_tasks")
        ).one() == (250, 250, None, 0, None)
    for sql in [
        "UPDATE quota_buckets SET reserved=-1",
        "UPDATE users SET membership_revision=-1",
        "UPDATE report_tasks SET generation=-1",
        "UPDATE quota_buckets SET reserved=NULL",
    ]:
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text(sql))
    inspector = inspect(engine)
    assert {c["name"] for c in inspector.get_check_constraints("quota_buckets")} >= {
        "ck_quota_bucket_nonnegative",
        "ck_quota_bucket_window",
    }
    assert {ix["name"] for ix in inspector.get_indexes("recharge_orders")} >= {
        "uq_recharge_order_user_key",
        "uq_recharge_order_provider_tx",
        "uq_recharge_order_refund_ref",
    }
    assert not next(c for c in inspector.get_columns("quota_buckets") if c["name"] == "reserved")["nullable"]
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO billing_operations (user_id,kind,idempotency_key,fingerprint,source,profile,model_sha256,units,status,catalog_version) VALUES (1,'position','one','fp','wallet','normal','sha',1,'reserved','membership_20261102_v1')"
            )
        )
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO billing_operations (user_id,kind,idempotency_key,fingerprint,source,profile,model_sha256,units,status,catalog_version) VALUES (1,'position','one','different','wallet','normal','sha',1,'reserved','membership_20261102_v1')"
                )
            )
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE billing_operations SET result=CAST(:result AS JSON)"), {"result": '"' + "围" * 22000 + '"'}
            )


def test_actual_postgres_test_identity_passes_readonly_runtime_guard(membership_pg_schema_engine, monkeypatch):
    engine = membership_pg_schema_engine
    monkeypatch.setenv("KATRAIN_DATABASE_URL", engine.url.render_as_string(hide_password=False))
    settings = Settings(
        KATRAIN_ENVIRONMENT="test", PAYMENTS_MODE="mock", MEMBERSHIP_MODE="enabled", BILLING_ENFORCED=True
    )
    assert billing_environment.validate_runtime_environment(engine, settings) is True
    assert inspect(engine).get_table_names() == []
