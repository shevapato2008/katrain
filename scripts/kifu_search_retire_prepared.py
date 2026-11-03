#!/usr/bin/env python3
"""Retire only the six replaced search relations, after runtime migration.

Plan is read-only. Apply requires an exact database name and operator evidence
that the inspected web, cron and receiver have loaded the published replacement.
No business tables, shared indexes, SGF, receipts or other triggers are removed.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text

INPUT_TABLES = (
    "kifu_players", "kifu_events", "kifu_event_editions", "kifu_player_aliases", "kifu_event_aliases",
    "kifu_player_names", "kifu_event_names", "kifu_raw_player_values", "kifu_raw_event_values",
    "kifu_raw_player_names", "kifu_raw_event_names", "kifu_name_batches", "kifu_name_changes",
    "kifu_name_research_evidence", "kifu_name_source_registry", "kifu_albums", "kifu_album_sources",
    "kifu_sources", "kifu_album_event_selections", "kifu_event_selection_batches",
)
DERIVED_TABLES = tuple("kifu_search_prepared_" + suffix for suffix in (
    "members", "dependencies", "displays", "names", "dirty", "state"
))
FUNCTION_NAME = "kifu_prepared_invalidate"
_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def qualified(schema, name):
    if not _IDENTIFIER.fullmatch(schema) or not _IDENTIFIER.fullmatch(name):
        raise ValueError("invalid schema or relation identifier")
    return f'"{schema}"."{name}"'


def inspect_target(conn, schema, expected_database):
    if conn.dialect.name != "postgresql":
        raise ValueError("retirement requires an explicitly selected PostgreSQL database")
    actual = conn.scalar(text("SELECT current_database()"))
    if actual != expected_database:
        raise ValueError("database does not match --expected-database")
    rows = conn.execute(text("""
        SELECT c.relname, pg_total_relation_size(c.oid) AS bytes
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=:schema AND c.relname=ANY(:names)
    """), {"schema": schema, "names": list(DERIVED_TABLES)}).mappings().all()
    state_name = qualified(schema, DERIVED_TABLES[-1])
    enabled = False
    if any(row["relname"] == DERIVED_TABLES[-1] for row in rows):
        states = conn.execute(text(f"SELECT enabled FROM {state_name}")).scalars().all()
        enabled = any(states)
    triggers = conn.execute(text("""
        SELECT t.tgname, c.relname AS table_name, p.proname AS function_name,
               pn.nspname AS function_schema
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace pn ON pn.oid=p.pronamespace
        WHERE NOT t.tgisinternal AND n.nspname=:schema AND p.proname=:function
    """), {"schema": schema, "function": FUNCTION_NAME}).mappings().all()
    expected = {f"kifu_prepared_{table}_{suffix}": table for table in INPUT_TABLES for suffix in ("dml", "truncate")}
    for trigger in triggers:
        if (expected.get(trigger["tgname"]) != trigger["table_name"]
                or trigger["function_schema"] != schema):
            raise ValueError("unexpected dependency on retired trigger function; investigate without CASCADE")
    function_exists = conn.scalar(text("SELECT to_regprocedure(:name) IS NOT NULL"),
                                  {"name": qualified(schema, FUNCTION_NAME) + "()"})
    maintainers = conn.scalar(text("""
        SELECT count(*) FROM pg_stat_activity
        WHERE datname=current_database() AND pid<>pg_backend_pid() AND state<>'idle'
          AND (application_name LIKE 'kifu_prepare%' OR query LIKE '%kifu_search_prepared_%')
    """))
    return {"database": actual, "schema": schema, "tables": [dict(row) for row in rows],
            "total_relation_bytes": sum(row["bytes"] for row in rows), "prepared_enabled": enabled,
            "active_prepared_transactions": maintainers, "triggers": [dict(row) for row in triggers],
            "drop_tables": [qualified(schema, name) for name in DERIVED_TABLES],
            "drop_function": qualified(schema, FUNCTION_NAME), "function_exists": function_exists, "drop_behavior": "RESTRICT"}


def apply_retirement(engine, *, schema, expected_database, runtime_build_sha, writers_quiescent):
    if not re.fullmatch(r"[0-9a-f]{40}", runtime_build_sha or "") or not writers_quiescent:
        raise ValueError("verified published runtime SHA and quiescent writers are required")
    # These are the existing publication/name/event guards. The outer guard
    # remains on its independent connection and is never retaken by the inner.
    from katrain.kifu_ingest.catalog import _publication_guard
    from katrain.web.kifu.name_batch import _locked_write

    commit_possible = False
    try:
        with _publication_guard(engine):
            with _locked_write(engine, lock_timeout_ms=1000, _search_maintenance=True,
                               _table_lock="SET LOCAL statement_timeout = '30s'") as conn:
                plan = inspect_target(conn, schema, expected_database)
                if plan["prepared_enabled"] or plan["active_prepared_transactions"]:
                    raise ValueError("prepared search must be disabled with no active maintenance transaction")
                for trigger in plan["triggers"]:
                    name = trigger["tgname"]
                    conn.exec_driver_sql(f'DROP TRIGGER "{name}" ON {qualified(schema, trigger["table_name"])} RESTRICT')
                conn.exec_driver_sql(f"DROP FUNCTION IF EXISTS {qualified(schema, FUNCTION_NAME)}() RESTRICT")
                for table in DERIVED_TABLES:
                    conn.exec_driver_sql(f"DROP TABLE IF EXISTS {qualified(schema, table)} RESTRICT")
                # _locked_write commits only after all RESTRICT drops succeed.
                commit_possible = True
    except BaseException:
        if not commit_possible:
            raise
        # A failed COMMIT/unlock response cannot justify another DROP attempt.
        # Resolve only from fresh catalog reads; never retry the mutation here.
        try:
            with engine.connect().execution_options(
                    isolation_level="REPEATABLE READ", postgresql_readonly=True) as verify:
                verify.exec_driver_sql("SET LOCAL lock_timeout = '1s'")
                verify.exec_driver_sql("SET LOCAL statement_timeout = '30s'")
                observed = inspect_target(verify, schema, expected_database)
        except Exception:
            raise RuntimeError("retirement commit outcome unknown; inspect pg_catalog before any retry") from None
        if observed["tables"] or observed["triggers"] or observed["function_exists"]:
            def presence(value):
                return ({row["relname"] for row in value["tables"]},
                        {row["tgname"] for row in value["triggers"]}, value["function_exists"])
            if presence(observed) == presence(plan):
                raise RuntimeError("retirement not committed; observed original relations, no automatic retry") from None
            raise RuntimeError("retirement commit outcome unknown (mixed catalog presence); stop before any retry") from None
        return {"runtime_build_sha": runtime_build_sha, "before": plan, "after": observed,
                "committed": True, "commit_verified_after_lost_response": True}
    with engine.connect() as conn:
        final = inspect_target(conn, schema, expected_database)
    if final["tables"] or final["triggers"] or final["function_exists"]:
        raise RuntimeError("retirement commit did not remove every explicitly selected relation")
    return {"runtime_build_sha": runtime_build_sha, "before": plan, "after": final, "committed": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true")
    action.add_argument("--apply", action="store_true")
    parser.add_argument("--schema", default="public")
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--runtime-build-sha")
    parser.add_argument("--writers-quiescent", action="store_true")
    args = parser.parse_args(argv)
    qualified(args.schema, FUNCTION_NAME)
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"], echo=False)
    try:
        if args.plan:
            with engine.connect().execution_options(isolation_level="REPEATABLE READ", postgresql_readonly=True) as conn:
                result = inspect_target(conn, args.schema, args.expected_database)
            result["runtime_build_sha"] = args.runtime_build_sha
            result["writers_quiescent"] = args.writers_quiescent
            result["apply_requires"] = "loaded web/cron/receiver, accepted ES, disabled prepared, no prepare process, quiescent writers"
        else:
            result = apply_retirement(engine, schema=args.schema, expected_database=args.expected_database,
                                      runtime_build_sha=args.runtime_build_sha, writers_quiescent=args.writers_quiescent)
        print(json.dumps(result, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
