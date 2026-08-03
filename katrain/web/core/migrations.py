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

# These tables hold authoritative player rank state and its immutable
# idempotency ledger. Like billing data, schema drift must never rebuild them.
AI_LADDER_TABLES = {"ai_ladder_profiles", "ai_ladder_game_ledger"}
PROTECTED_TABLES = BILLING_TABLES | AI_LADDER_TABLES


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
            # Check bool before int: PostgreSQL rejects `BOOLEAN DEFAULT 0` (needs
            # TRUE/FALSE). SQLite 3.23+ also accepts TRUE/FALSE, so this works on both.
            if "bool" in type_name:
                return "FALSE"
            if "int" in type_name or "numeric" in type_name or "float" in type_name:
                return "0"
            return "''"
        return None
    value = default.arg
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
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


def backfill_ai_ladder_decisions(engine) -> None:
    """Mark rows from the pre-decision ledger schema as counted valid games.

    The old table admitted only certified, available ``ai_ladder_ranked``
    win/loss rows. ``add_missing_columns`` adds ``counted`` as FALSE and
    ``reason`` as NULL; this idempotent update restores their original meaning
    without rebuilding or dropping the protected ledger.
    """

    inspector = inspect(engine)
    table_name = "ai_ladder_game_ledger"
    if table_name not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    required = {
        "counted",
        "reason",
        "result",
        "game_type",
        "opponent_rung",
        "opponent_rank_name",
        "opponent_config_snapshot",
        "opponent_certification_status",
        "opponent_availability",
        "opponent_route",
    }
    if not required.issubset(columns):
        return

    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE ai_ladder_game_ledger SET counted = TRUE "
                "WHERE counted = FALSE AND reason IS NULL "
                "AND result IN ('win', 'loss') AND game_type = 'ai_ladder_ranked' "
                "AND opponent_rung BETWEEN 1 AND 41 AND opponent_rank_name IS NOT NULL "
                "AND opponent_config_snapshot IS NOT NULL "
                "AND opponent_certification_status = 'certified' "
                "AND opponent_availability = 'available' "
                "AND opponent_route IN ('local', 'server')"
            )
        )
        if result.rowcount:
            logger.info("migrate: marked %s legacy AI ladder decisions counted", result.rowcount)
