"""Phone authentication DDL is isolated, idempotent and fails closed on drift."""

import pytest
from sqlalchemy import create_engine, inspect, text

from katrain.web.core import migrations, models_db
from tests.web_ui.membership_test_support import membership_pg_schema_engine


PHONE_TABLES = {"phone_identities", "phone_signup_claims", "sms_phone_state", "sms_challenges", "sms_send_buckets"}


def test_phone_authentication_has_owned_schema_entrypoint():
    assert callable(getattr(migrations, "migrate_phone_auth_schema", None)), "Phone authentication migration missing"
    assert PHONE_TABLES <= set(models_db.Base.metadata.tables)


def test_phone_schema_migration_is_explicit_and_idempotent(membership_pg_schema_engine):
    engine = membership_pg_schema_engine
    migrate = getattr(migrations, "migrate_phone_auth_schema", None)
    assert callable(migrate), "Phone authentication needs its named safe migration"
    # This migration does not own users or any pre-existing balance.
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, credits INTEGER NOT NULL)"))
        conn.execute(text("INSERT INTO users VALUES (7, 23456)"))
    migrate(engine)
    migrate(engine)
    migrations.verify_phone_auth_schema(engine)
    assert set(inspect(engine).get_table_names()) == PHONE_TABLES | {"users"}
    assert PHONE_TABLES <= migrations.PROTECTED_TABLES
    with engine.connect() as conn:
        assert conn.execute(text("SELECT credits FROM users WHERE id=7")).scalar_one() == 23456
    assert set(inspect(engine).get_pk_constraint("sms_send_buckets")["constrained_columns"]) == {
        "kind",
        "key",
        "window_start",
    }
    for table, columns in (
        ("phone_identities", {"phone_e164"}),
        ("phone_identities", {"user_id"}),
        ("phone_signup_claims", {"grant_ref"}),
    ):
        assert any(set(item["column_names"]) == columns for item in inspect(engine).get_unique_constraints(table))
    assert inspect(engine).get_foreign_keys("phone_signup_claims") == []


def test_phone_schema_existing_wrong_unique_fails_closed(membership_pg_schema_engine):
    engine = membership_pg_schema_engine
    migrate = getattr(migrations, "migrate_phone_auth_schema", None)
    assert callable(migrate), "Phone authentication needs its named safe migration"
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
    migrate(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE phone_identities DROP CONSTRAINT uq_phone_identity_user"))
    with pytest.raises(RuntimeError, match="phone authentication schema"):
        migrate(engine)
    assert "phone_identities" in inspect(engine).get_table_names()


@pytest.mark.parametrize("table,constraint,column", [
    ("sms_phone_state", "ck_sms_phone_error_count", "error_count"),
    ("sms_send_buckets", "ck_sms_send_bucket_count", "count"),
])
def test_phone_schema_same_named_reverse_nonnegative_check_fails_closed(
    membership_pg_schema_engine, table, constraint, column
):
    engine = membership_pg_schema_engine
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
    migrations.migrate_phone_auth_schema(engine)
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT {constraint}"))
        conn.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {constraint} CHECK ({column} <= 0)"))
    with pytest.raises(RuntimeError, match="phone authentication schema: check constraint drift"):
        migrations.migrate_phone_auth_schema(engine)


def test_sqlite_phone_nonnegative_checks_accept_native_format_on_repeat_migration():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        migrations.migrate_phone_auth_schema(engine)
        migrations.migrate_phone_auth_schema(engine)
    finally:
        engine.dispose()


def test_phone_claim_outlives_deleted_user(membership_pg_schema_engine):
    engine = membership_pg_schema_engine
    migrate = getattr(migrations, "migrate_phone_auth_schema", None)
    assert callable(migrate), "Phone authentication needs its named safe migration"
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        conn.execute(text("INSERT INTO users VALUES (9)"))
    migrate(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO phone_signup_claims (phone_e164, claim_type, user_id) "
                "VALUES ('+8613800000011', 'bound_existing', 9)"
            )
        )
        conn.execute(text("INSERT INTO phone_identities (phone_e164, user_id) VALUES ('+8613800000011', 9)"))
        conn.execute(text("DELETE FROM users WHERE id=9"))
        assert conn.execute(text("SELECT count(*) FROM phone_signup_claims")).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM phone_identities")).scalar_one() == 0


@pytest.mark.parametrize("drift", ["claim_fk", "missing_cascade"])
def test_phone_schema_rejects_claim_fk_and_missing_identity_cascade(membership_pg_schema_engine, drift):
    engine = membership_pg_schema_engine
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
    migrations.migrate_phone_auth_schema(engine)
    with engine.begin() as conn:
        if drift == "claim_fk":
            conn.execute(
                text(
                    "ALTER TABLE phone_signup_claims ADD CONSTRAINT incorrect_audit_fk "
                    "FOREIGN KEY (user_id) REFERENCES users(id)"
                )
            )
        else:
            conn.execute(text("ALTER TABLE phone_identities DROP CONSTRAINT phone_identities_user_id_fkey"))
            conn.execute(
                text(
                    "ALTER TABLE phone_identities ADD CONSTRAINT phone_identities_user_id_fkey "
                    "FOREIGN KEY (user_id) REFERENCES users(id)"
                )
            )
    with pytest.raises(RuntimeError, match="phone authentication schema"):
        migrations.verify_phone_auth_schema(engine)
