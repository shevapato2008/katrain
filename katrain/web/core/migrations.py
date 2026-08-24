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
# 象棋升降级的四张表已随模块搬去 lobby-platform(ranked_api/xiangqi/),这里不再有对应
# 的 ORM 模型。已部署的库里那四张表**原样留着**:drift 循环只遍历
# `models_db.Base.metadata.sorted_tables`,模型没了就永远进不了 drop 名单,数据不会被动。
PROTECTED_TABLES = BILLING_TABLES | AI_LADDER_TABLES | {AI_LADDER_LEGACY_TABLE}

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
        # 🔴 这里原本是 `postgres_ai_ladder_decision_statements(set(columns), checks)` ——
        # 位置参数调一个**只收关键字参数**的函数(定义见下,签名是 `*, existing_columns,
        # existing_checks`),必然 TypeError。也就是说 **PG 上的旧库升级分支从来没跑通过**。
        # SQLite 走的是上面那一支,所以本机测试永远碰不到它 —— 又一例
        # 「保证在本机不存在而不会红」。
        statements = postgres_ai_ladder_decision_statements(existing_columns=set(columns), existing_checks=checks)
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


AI_LADDER_ACCOUNT_SUBJECT_CONDITION = "account_subject IS NULL OR length(account_subject) BETWEEN 1 AND 32"

ACCOUNT_SUBJECT_CONSTRAINT = "ck_ai_ladder_ledger_account_subject_len"


def postgres_ai_ladder_account_subject_statements(*, existing_checks: set[str]) -> list[str]:
    """把账本主体长度约束补到已存在的 PostgreSQL 表上。"""

    if ACCOUNT_SUBJECT_CONSTRAINT in existing_checks:
        return []
    return [
        f"ALTER TABLE ai_ladder_game_ledger ADD CONSTRAINT {ACCOUNT_SUBJECT_CONSTRAINT} "
        f"CHECK ({AI_LADDER_ACCOUNT_SUBJECT_CONDITION})"
    ]


def enforce_ai_ladder_account_subject_schema(engine) -> None:
    """账本主体长度约束,不重建这张受保护的表就装上去。

    与三家共享账本的 `ck_ranked_ledgers_account_subject_len` 同源。SQLite 不能给
    已存在的表 `ADD CONSTRAINT`,所以那一支用触发器 —— 与本文件既有的
    `enforce_ai_ladder_terminal_audit_schema` 同形。

    落库前先点一遍存量:有不合规的行就抛,**不静默放过也不静默改数据**。
    """

    table = "ai_ladder_game_ledger"
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    if "account_subject" not in {column["name"] for column in inspector.get_columns(table)}:
        return

    checks = {constraint.get("name") for constraint in inspector.get_check_constraints(table)}
    if ACCOUNT_SUBJECT_CONSTRAINT in checks:
        return

    with engine.begin() as conn:
        invalid = conn.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE NOT ({AI_LADDER_ACCOUNT_SUBJECT_CONDITION})")
        ).scalar_one()
        if invalid:
            raise RuntimeError(f"AI ladder account_subject migration found {invalid} invalid row(s)")

        if engine.dialect.name == "sqlite":
            # ⚠️ **不是** `CREATE TRIGGER IF NOT EXISTS` —— 那是按名字跳过、不看内容的,
            # 名字没变而内容变了就一行都不执行,长命的库留旧规则、新建的库拿新规则,
            # 两边分叉且全绿。先删后建。(本文件 :242 那个终局审计触发器仍是旧写法,
            # 是同一个坑的另一处实例,不在本次范围内 —— 别照抄它。)
            condition = AI_LADDER_ACCOUNT_SUBJECT_CONDITION.replace("account_subject", "NEW.account_subject")
            for action in ("INSERT", "UPDATE"):
                trigger = f"trg_ai_ladder_ledger_account_subject_{action.lower()}"
                conn.execute(text(f'DROP TRIGGER IF EXISTS "{trigger}"'))
                conn.execute(
                    text(
                        f'CREATE TRIGGER "{trigger}" BEFORE {action} ON "{table}" '
                        f"FOR EACH ROW WHEN NOT ({condition}) "
                        "BEGIN SELECT RAISE(ABORT, 'invalid AI ladder account subject'); END"
                    )
                )
        elif engine.dialect.name == "postgresql":
            for statement in postgres_ai_ladder_account_subject_statements(existing_checks=checks):
                conn.execute(text(statement))


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
    enforce_ai_ladder_terminal_audit_schema(engine)
    enforce_ai_ladder_account_subject_schema(engine)


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
                # Let SQLAlchemy compile dialect clauses such as partial unique
                # predicates. Reconstructing an index from column names would
                # silently turn it into a global unique constraint.
                index.create(bind=conn, checkfirst=True)
                logger.info(f"migrate: created index {index.name} on {table.name}")


KIFU_SORT_INDEX = "ix_kifu_albums_date_sort_desc_id_desc"


def create_kifu_album_sort_index(engine) -> None:
    """给棋谱库列表的 ORDER BY 配一条真能用上的索引（**仅 PostgreSQL**）。

    `/api/v1/kifu/albums` 按 ``date_sort DESC NULLS LAST, id DESC`` 排。现有的
    ``btree(date_sort)`` 是默认的 ASC NULLS LAST，**反向扫出来是 DESC NULLS
    FIRST**——不是同一个顺序，所以规划器只能全表扫 247MB 的堆再排 151,197 行，
    每翻一页做两遍（COUNT 一遍、取页一遍）。

    2026-08-24 在与生产同一份数据（151,197 行 / 247MB）的测试库上实测：

    ==========  ========  =========
    查询        建索引前  建索引后
    ==========  ========  =========
    取当页      364ms     0.13ms（读 9 个 buffer，不是 31,707）
    COUNT       557ms     25ms（index-only scan，排序一并消失）
    端到端接口  1.30s     0.18s
    ==========  ========  =========

    **为什么不写进 ``__table_args__``**：SQLAlchemy 对所有方言都照样渲染
    ``NULLS LAST``，而 SQLite 在 CREATE INDEX 里直接拒绝它
    （``unsupported use of NULLS LAST``，sqlite 3.51 实测），
    那会让每一次 SQLite 启动都挂在 ``create_missing_indexes`` 上。
    跑 SQLite 的部署（kiosk / 盒端）不会有这个量级的棋谱库。

    不用 CONCURRENTLY：它不能在事务块里跑，而这里是启动期的一次性建索引，
    151k 行实测约 600ms。
    """

    if engine.dialect.name != "postgresql":
        return
    inspector = inspect(engine)
    if "kifu_albums" not in inspector.get_table_names():
        return
    if KIFU_SORT_INDEX in {ix["name"] for ix in inspector.get_indexes("kifu_albums")}:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {KIFU_SORT_INDEX} "
                "ON kifu_albums (date_sort DESC NULLS LAST, id DESC)"
            )
        )
    logger.info(f"migrate: created index {KIFU_SORT_INDEX} on kifu_albums")


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
