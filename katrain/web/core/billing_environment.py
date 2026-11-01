"""Read-only deployment boundary before startup DDL or TEST payment writes.

The independently provisioned billing_test_identity schema is never created or
updated by application code. Environment variables alone cannot mark a DB TEST.
"""

import os

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from katrain.web.core import models_db

ACTIVATION_KEY = "membership_activated_v1"


def _membership_facts_exist(connection) -> bool:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if (
        "system_config" in tables
        and connection.execute(text("SELECT 1 FROM system_config WHERE key = :key"), {"key": ACTIVATION_KEY}).first()
    ):
        return True
    for table, version_column in (
        ("membership_terms", None),
        ("billing_operations", None),
        ("report_tasks", "billing_version"),
        ("recharge_orders", "catalog_version"),
    ):
        if table not in tables:
            continue
        condition = ""
        if version_column:
            if version_column not in {column["name"] for column in inspector.get_columns(table)}:
                continue
            condition = f' WHERE "{version_column}" IS NOT NULL'
        if connection.execute(text(f'SELECT 1 FROM "{table}"{condition} LIMIT 1')).first():
            return True
    return False


def validate_runtime_environment(engine, settings) -> bool:
    """Fail closed before DDL; return True only for a verified TEST mock DB.

    Call again before mock order writes. Checks use the bound engine's actual
    current_database(), independent of the application's default/config URL.
    """
    mode = settings.MEMBERSHIP_MODE
    if mode not in {"legacy", "enabled", "paused"}:
        raise RuntimeError("Unknown MEMBERSHIP_MODE")
    if mode != "legacy" and not settings.BILLING_ENFORCED:
        raise RuntimeError("MEMBERSHIP_MODE requires BILLING_ENFORCED=true")
    verified_test = False
    if settings.PAYMENTS_MODE == "mock":
        if settings.KATRAIN_ENVIRONMENT not in {"test", "development"}:
            raise RuntimeError("Mock payments are forbidden in production")
        explicit_url = os.getenv("KATRAIN_DATABASE_URL")
        if not explicit_url:
            raise RuntimeError("Mock payments require explicit KATRAIN_DATABASE_URL")
        if engine.dialect.name != "postgresql":
            raise RuntimeError("Mock payments require an independently marked PostgreSQL TEST database")
        try:
            expected_database = make_url(explicit_url).database
            with engine.connect() as connection:
                actual_database = connection.execute(text("SELECT current_database()")).scalar_one()
                if (
                    not expected_database
                    or actual_database != expected_database
                    or engine.url.database != actual_database
                ):
                    raise RuntimeError("Mock payment database identity does not match explicit database")
                marker = connection.execute(
                    text("SELECT environment FROM billing_test_identity.environment WHERE database_name = :database"),
                    {"database": actual_database},
                ).scalar_one_or_none()
                if marker != "TEST":
                    raise RuntimeError("Database has no independently provisioned TEST identity")
        except RuntimeError:
            raise
        except Exception as exc:
            # Do not interpolate connection errors/DSNs, which may contain secrets.
            raise RuntimeError("Cannot verify independent TEST database identity") from None
        verified_test = True
    if mode == "legacy":
        with engine.connect() as connection:
            if _membership_facts_exist(connection):
                raise RuntimeError("Membership was activated; refusing downgrade to legacy")
    return verified_test


def activate_membership_mode(session, settings) -> None:
    """Persist activation using the caller's transaction; never commit here."""
    if settings.MEMBERSHIP_MODE not in {"enabled", "paused"}:
        return
    if not settings.BILLING_ENFORCED:
        raise RuntimeError("Membership activation requires BILLING_ENFORCED=true")
    if session.get(models_db.SystemConfigDB, ACTIVATION_KEY) is None:
        session.add(
            models_db.SystemConfigDB(
                key=ACTIVATION_KEY, value="1", description="Membership billing activated; legacy downgrade prohibited"
            )
        )
        session.flush()
