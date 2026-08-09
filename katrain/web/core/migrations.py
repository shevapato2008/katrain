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
AI_LADDER_TABLES = {
    "ai_ladder_profiles",
    "ai_ladder_game_ledger",
    "ai_ladder_pending_games",
    "ai_ladder_active_games",
}
AI_LADDER_LEGACY_TABLE = "ai_ladder_game_ledger_legacy_v1"
XIANGQI_RANKED_TABLES = {
    "xiangqi_rating_profiles",
    "xiangqi_ranked_reservations",
    "xiangqi_ranked_ledger",
    "xiangqi_ranked_capability_jtis",
}
PROTECTED_TABLES = BILLING_TABLES | AI_LADDER_TABLES | XIANGQI_RANKED_TABLES | {AI_LADDER_LEGACY_TABLE}


def install_xiangqi_ranked_immutability(engine) -> None:
    """Install idempotent database triggers that make terminal facts append-only."""

    if "xiangqi_ranked_ledger" not in inspect(engine).get_table_names():
        return
    if engine.dialect.name == "sqlite":
        statements = (
            "CREATE TRIGGER IF NOT EXISTS trg_xiangqi_ranked_ledger_no_update "
            "BEFORE UPDATE ON xiangqi_ranked_ledger BEGIN "
            "SELECT RAISE(ABORT, 'xiangqi ranked ledger is immutable'); END",
            "CREATE TRIGGER IF NOT EXISTS trg_xiangqi_ranked_ledger_no_delete "
            "BEFORE DELETE ON xiangqi_ranked_ledger BEGIN "
            "SELECT RAISE(ABORT, 'xiangqi ranked ledger is immutable'); END",
        )
    elif engine.dialect.name == "postgresql":
        statements = (
            "CREATE OR REPLACE FUNCTION reject_xiangqi_ranked_ledger_mutation() RETURNS trigger AS $$ "
            "BEGIN RAISE EXCEPTION 'xiangqi ranked ledger is immutable'; END; $$ LANGUAGE plpgsql",
            "DROP TRIGGER IF EXISTS trg_xiangqi_ranked_ledger_no_update ON xiangqi_ranked_ledger",
            "CREATE TRIGGER trg_xiangqi_ranked_ledger_no_update BEFORE UPDATE ON xiangqi_ranked_ledger "
            "FOR EACH ROW EXECUTE FUNCTION reject_xiangqi_ranked_ledger_mutation()",
            "DROP TRIGGER IF EXISTS trg_xiangqi_ranked_ledger_no_delete ON xiangqi_ranked_ledger",
            "CREATE TRIGGER trg_xiangqi_ranked_ledger_no_delete BEFORE DELETE ON xiangqi_ranked_ledger "
            "FOR EACH ROW EXECUTE FUNCTION reject_xiangqi_ranked_ledger_mutation()",
        )
    else:
        raise RuntimeError(f"unsupported Xiangqi ranked ledger dialect: {engine.dialect.name}")

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _fail_on_xiangqi_ranked_column_drift(engine, inspector) -> None:
    existing_tables = set(inspector.get_table_names())
    for table_name in XIANGQI_RANKED_TABLES & existing_tables:
        expected = {column.name for column in models_db.Base.metadata.tables[table_name].columns}
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        missing = expected - actual
        if missing:
            raise RuntimeError(
                f"schema drift in protected table {table_name}: missing columns {sorted(missing)!r}; "
                "refusing generic rebuild"
            )

AI_LADDER_TERMINAL_AUDIT_CONDITION = (
    "(terminal_source IS NULL AND origin_device_id IS NULL "
    "AND deciding_device_id IS NULL AND decided_at IS NULL) OR "
    "(terminal_source IS NOT NULL "
    "AND terminal_source IN ('played_result', 'remote_resign', 'recovery') "
    "AND origin_device_id IS NOT NULL AND deciding_device_id IS NOT NULL AND decided_at IS NOT NULL)"
)


def migrate_ai_ladder_decision_schema(engine) -> None:
    """Upgrade the short-lived valid-only ledger without deleting history.

    SQLite cannot relax NOT NULL or CHECK constraints in place, so the old
    table is retained under a protected backup name while a final decision
    ledger is created and populated. PostgreSQL can make the same changes with
    non-destructive ALTER statements.
    """

    table_name = "ai_ladder_game_ledger"
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if table_name not in tables:
        if engine.dialect.name == "sqlite" and AI_LADDER_LEGACY_TABLE in tables:
            raise RuntimeError("AI ladder legacy backup exists without final decision ledger")
        return

    columns = {column["name"]: column for column in inspector.get_columns(table_name)}
    already_final = "counted" in columns and columns.get("opponent_rung", {}).get("nullable", False)
    if already_final:
        if engine.dialect.name == "sqlite" and AI_LADDER_LEGACY_TABLE in tables:
            _validate_sqlite_ai_ladder_backup(engine)
        return

    if engine.dialect.name == "sqlite":
        _migrate_sqlite_ai_ladder_decision_schema(engine, inspector)
    elif engine.dialect.name == "postgresql":
        checks = {constraint.get("name") for constraint in inspector.get_check_constraints(table_name)}
        statements = postgres_ai_ladder_decision_statements(set(columns), checks)
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))


def _validate_sqlite_ai_ladder_backup(engine) -> None:
    """Fail closed unless every preserved v1 decision is identical and counted."""

    table_name = "ai_ladder_game_ledger"
    with engine.connect() as conn:
        missing = conn.execute(
            text(
                f'SELECT COUNT(*) FROM "{AI_LADDER_LEGACY_TABLE}" legacy '
                f'LEFT JOIN "{table_name}" current ON current.game_id = legacy.game_id '
                "WHERE current.game_id IS NULL"
            )
        ).scalar_one()
        if missing:
            raise RuntimeError(
                f"AI ladder migration incomplete: {missing} legacy decision(s) missing from final ledger"
            )

        compared_columns = (
            "id",
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
        )
        differences = " OR ".join(f"current.{column} IS NOT legacy.{column}" for column in compared_columns)
        inconsistent = conn.execute(
            text(
                f'SELECT COUNT(*) FROM "{AI_LADDER_LEGACY_TABLE}" legacy '
                f'JOIN "{table_name}" current ON current.game_id = legacy.game_id '
                f"WHERE current.counted IS NOT TRUE OR current.reason IS NOT NULL OR {differences}"
            )
        ).scalar_one()
        if inconsistent:
            raise RuntimeError(
                f"AI ladder migration incomplete: {inconsistent} legacy decision(s) inconsistent with final ledger"
            )


def _migrate_sqlite_ai_ladder_decision_schema(engine, inspector) -> None:
    table_name = "ai_ladder_game_ledger"
    existing_tables = set(inspector.get_table_names())
    if AI_LADDER_LEGACY_TABLE in existing_tables:
        # The caller already established that the current table is not final.
        # A backup beside another legacy-shaped table indicates a partial or
        # manually altered migration and must not be silently accepted.
        raise RuntimeError("AI ladder legacy backup exists without a final decision ledger")

    index_names = [index["name"] for index in inspector.get_indexes(table_name) if index.get("name")]
    with engine.begin() as conn:
        for index_name in index_names:
            conn.execute(text(f'DROP INDEX IF EXISTS "{index_name}"'))
        conn.execute(text(f'ALTER TABLE "{table_name}" RENAME TO "{AI_LADDER_LEGACY_TABLE}"'))
        models_db.AiLadderGameLedger.__table__.create(bind=conn)
        conn.execute(
            text(
                f'INSERT INTO "{table_name}" '
                "(id, game_id, user_id, user_color, result, game_type, opponent_rung, opponent_rank_name, "
                "opponent_config_snapshot, opponent_certification_status, opponent_availability, opponent_route, "
                "counted, reason, settled_at) "
                f"SELECT id, game_id, user_id, user_color, result, game_type, opponent_rung, opponent_rank_name, "
                "opponent_config_snapshot, opponent_certification_status, opponent_availability, opponent_route, "
                f'TRUE, NULL, settled_at FROM "{AI_LADDER_LEGACY_TABLE}"'
            )
        )
        logger.info("migrate: retained %s and created unified AI ladder decision ledger", AI_LADDER_LEGACY_TABLE)


def postgres_ai_ladder_decision_statements(*, existing_columns: set[str], existing_checks: set[str]) -> list[str]:
    """Return auditable PostgreSQL DDL for the valid-only to decision ledger upgrade."""

    table = "ai_ladder_game_ledger"
    statements = []
    if "counted" not in existing_columns:
        statements.append(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS counted BOOLEAN")
    if "reason" not in existing_columns:
        statements.append(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS reason VARCHAR(32)")
    statements.extend(
        [
            f"UPDATE {table} SET counted = TRUE WHERE "
            "(counted IS NULL OR (counted = FALSE AND reason IS NULL)) AND result IN ('win', 'loss') "
            "AND game_type = 'ai_ladder_ranked'",
            f"ALTER TABLE {table} ALTER COLUMN counted SET DEFAULT FALSE",
            f"ALTER TABLE {table} ALTER COLUMN counted SET NOT NULL",
        ]
    )
    for column in (
        "opponent_rung",
        "opponent_rank_name",
        "opponent_config_snapshot",
        "opponent_certification_status",
        "opponent_availability",
        "opponent_route",
    ):
        statements.append(f"ALTER TABLE {table} ALTER COLUMN {column} DROP NOT NULL")
    for constraint in (
        "ck_ai_ladder_ledger_result",
        "ck_ai_ladder_ledger_game_type",
        "ck_ai_ladder_ledger_certification",
        "ck_ai_ladder_ledger_availability",
    ):
        if constraint in existing_checks:
            statements.append(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}")
    if "ck_ai_ladder_ledger_decision" not in existing_checks:
        statements.append(
            f"ALTER TABLE {table} ADD CONSTRAINT ck_ai_ladder_ledger_decision CHECK ("
            "(counted = FALSE AND reason IS NOT NULL) OR "
            "(counted = TRUE AND reason IS NULL AND opponent_rung IS NOT NULL "
            "AND opponent_rank_name IS NOT NULL AND opponent_config_snapshot IS NOT NULL "
            "AND opponent_certification_status = 'certified' AND opponent_availability = 'available' "
            "AND opponent_route IS NOT NULL AND result IN ('win', 'loss') "
            "AND game_type = 'ai_ladder_ranked'))"
        )
    return statements


def postgres_ai_ladder_terminal_audit_statements(*, existing_checks: set[str]) -> list[str]:
    """Return the non-destructive PostgreSQL constraint upgrade for provenance fields."""

    constraint = "ck_ai_ladder_ledger_terminal_audit"
    if constraint in existing_checks:
        return []
    return [
        f"ALTER TABLE ai_ladder_game_ledger ADD CONSTRAINT {constraint} "
        f"CHECK ({AI_LADDER_TERMINAL_AUDIT_CONDITION})"
    ]


def enforce_ai_ladder_terminal_audit_schema(engine) -> None:
    """Constrain terminal provenance without rebuilding the protected ledger."""

    table = "ai_ladder_game_ledger"
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    required = {"terminal_source", "origin_device_id", "deciding_device_id", "decided_at"}
    if not required.issubset({column["name"] for column in inspector.get_columns(table)}):
        return

    checks = {constraint.get("name") for constraint in inspector.get_check_constraints(table)}
    if "ck_ai_ladder_ledger_terminal_audit" in checks:
        return

    with engine.begin() as conn:
        invalid = conn.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE NOT ({AI_LADDER_TERMINAL_AUDIT_CONDITION})")
        ).scalar_one()
        if invalid:
            raise RuntimeError(f"AI ladder terminal audit migration found {invalid} invalid row(s)")

        if engine.dialect.name == "sqlite":
            new_condition = AI_LADDER_TERMINAL_AUDIT_CONDITION
            for column in required:
                new_condition = new_condition.replace(column, f"NEW.{column}")
            for action in ("INSERT", "UPDATE"):
                trigger = f"trg_ai_ladder_ledger_terminal_audit_{action.lower()}"
                conn.execute(
                    text(
                        f'CREATE TRIGGER IF NOT EXISTS "{trigger}" BEFORE {action} ON "{table}" '
                        f"FOR EACH ROW WHEN NOT ({new_condition}) "
                        "BEGIN SELECT RAISE(ABORT, 'invalid AI ladder terminal audit provenance'); END"
                    )
                )
        elif engine.dialect.name == "postgresql":
            for statement in postgres_ai_ladder_terminal_audit_statements(existing_checks=checks):
                conn.execute(text(statement))


def add_missing_columns(engine) -> None:
    """ADD COLUMN for any model column missing from an existing table.

    Non-destructive and idempotent. Runs before the SQLite drift-rebuild check so
    that a simple new column (e.g. users.is_admin) doesn't trigger a full rebuild.
    """
    inspector = inspect(engine)
    _fail_on_xiangqi_ranked_column_drift(engine, inspector)
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
    enforce_ai_ladder_terminal_audit_schema(engine)


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
                # Let SQLAlchemy compile dialect clauses such as the Xiangqi
                # reservation's partial unique predicate. Reconstructing an
                # index from column names would silently turn it into a global
                # unique constraint and prevent a user from playing again.
                index.create(bind=conn, checkfirst=True)
                logger.info(f"migrate: created index {index.name} on {table.name}")
    install_xiangqi_ranked_immutability(engine)


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
