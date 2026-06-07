"""Lightweight, auditable schema migrations (no Alembic).

The project relies on Base.metadata.create_all for new tables, but that cannot
add columns/indexes to tables that already exist. This module performs only
non-destructive ALTERs (ADD COLUMN, CREATE INDEX) that work on both SQLite and
PostgreSQL, and it protects the billing/ledger tables from the SQLite
schema-drift "drop all and rebuild" fallback (those must never lose rows).
"""

import logging

from sqlalchemy import inspect, text

from katrain.web.core import models_db

logger = logging.getLogger("katrain_web")

# Tables holding financial/asset data — never drop these to "fix" schema drift.
BILLING_TABLES = {"credit_transactions", "redeem_codes", "recharge_orders"}


def add_missing_columns(engine) -> None:
    """ADD COLUMN for any model column missing from an existing table.

    Non-destructive and idempotent. Runs before the SQLite drift-rebuild check so
    that a simple new column (e.g. users.is_admin) doesn't trigger a full rebuild.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in models_db.Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing_cols:
                    continue
                col_type = col.type.compile(engine.dialect)
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}'
                default = _default_clause(col)
                if default is not None:
                    ddl += f" DEFAULT {default}"
                conn.execute(text(ddl))
                logger.info(f"migrate: added column {table.name}.{col.name}")


def _default_clause(col):
    """Render a literal DEFAULT for ADD COLUMN, when the model defines one."""
    default = getattr(col, "default", None)
    if default is None or not getattr(default, "is_scalar", False):
        if not col.nullable:
            # Non-null column with no scalar default — supply a safe zero/empty.
            type_name = col.type.__class__.__name__.lower()
            if "int" in type_name or "numeric" in type_name or "float" in type_name:
                return "0"
            if "bool" in type_name:
                return "0"
            return "''"
        return None
    value = default.arg
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return f"'{value}'"


def create_missing_indexes(engine) -> None:
    """CREATE INDEX IF NOT EXISTS for model-declared indexes missing in the DB."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in models_db.Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            existing_idx = {ix["name"] for ix in inspector.get_indexes(table.name)}
            for index in table.indexes:
                if index.name in existing_idx:
                    continue
                cols = ", ".join(f'"{c.name}"' for c in index.columns)
                unique = "UNIQUE " if index.unique else ""
                conn.execute(text(f'CREATE {unique}INDEX IF NOT EXISTS "{index.name}" ON "{table.name}" ({cols})'))
                logger.info(f"migrate: created index {index.name} on {table.name}")
