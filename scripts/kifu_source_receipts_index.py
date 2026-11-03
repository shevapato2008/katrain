"""Explicit PostgreSQL receipt-filter index; default inspection is read-only.

KATRAIN_DATABASE_URL selects the target; --apply additionally requires its exact
--expected-database. --analyze explicitly collects expression statistics after a
verified successful build. No startup hook, query change, or business-data write.
A timeout can leave an invalid index. Report its OID/definition/readiness and stop:
never retry, drop, or rebuild an existing object automatically. Long-lived old
snapshots can delay concurrent expression-index builds even without table writes.
"""

import argparse
import json
import os
import re
from time import monotonic

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

INDEX_NAME = "ix_kifu_name_batches_status_publication_format"
TABLE_NAME = "kifu_name_batches"
_IDENTIFIER = re.compile(r"[a-z_][a-z0-9_]{0,62}\Z")


def qualified(schema, name):
    if not _IDENTIFIER.fullmatch(schema) or not _IDENTIFIER.fullmatch(name):
        raise ValueError("invalid schema or relation identifier")
    return f'"{schema}"."{name}"'


def create_statement(schema="public"):
    return (
        f"CREATE INDEX CONCURRENTLY {INDEX_NAME} ON {qualified(schema,TABLE_NAME)} "
        "(status, (reviewed_artifact ->> 'publication_format'))"
    )


def _describe(conn, schema, expected_database=None):
    if conn.dialect.name != "postgresql":
        raise ValueError("receipt index operation requires PostgreSQL")
    table = qualified(schema, TABLE_NAME)
    database = conn.exec_driver_sql("SELECT current_database()").scalar_one()
    if expected_database is not None and database != expected_database:
        raise ValueError("database does not match --expected-database")
    target = conn.scalar(text("SELECT to_regclass(:table)::oid"), {"table": table})
    if target is None:
        raise ValueError("existing kifu_name_batches table is required")
    status = dict(
        database=database,
        schema=schema,
        table=TABLE_NAME,
        name=INDEX_NAME,
        oid=None,
        state="missing",
        valid=False,
        ready=False,
        definition_matches=False,
        definition=None,
        create_statement=create_statement(schema),
    )
    relation = (
        conn.execute(
            text(
                """SELECT c.oid,c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=:schema AND c.relname=:name"""
            ),
            dict(schema=schema, name=INDEX_NAME),
        )
        .mappings()
        .one_or_none()
    )
    if relation is None:
        return status
    status["oid"] = relation["oid"]
    if relation["relkind"] != "i":
        return {**status, "state": "mismatched"}
    row = (
        conn.execute(
            text(
                """SELECT i.indisvalid AS valid,i.indisready AS ready,i.indislive AS live,
        pg_get_indexdef(i.indexrelid) AS definition,
        (i.indrelid=:target AND am.amname='btree' AND i.indpred IS NULL AND NOT i.indisunique
         AND NOT i.indisexclusion AND i.indnkeyatts=2 AND i.indnatts=2
         AND i.indoption::text='0 0' AND c.reloptions IS NULL) AS full_btree
        FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid JOIN pg_am am ON am.oid=c.relam
        WHERE i.indexrelid=:oid"""
            ),
            dict(target=target, oid=relation["oid"]),
        )
        .mappings()
        .one()
    )
    # Individual-column deparsing omits COLLATE/opclass options. Compare the
    # complete key definition without stripping literals or index semantics.
    keys = row["definition"].partition(" USING btree ")[2]
    matches = row["full_btree"] and keys == "(status, ((reviewed_artifact ->> 'publication_format'::text)))"
    return {
        **status,
        **{key: row[key] for key in ("valid", "ready", "live", "definition")},
        "definition_matches": bool(matches),
        "state": (
            "mismatched" if not matches else ("ready" if row["valid"] and row["ready"] and row["live"] else "invalid")
        ),
    }


def check_index(engine, *, schema="public", expected_database=None):
    with engine.connect() as conn:
        if conn.dialect.name != "postgresql":
            raise ValueError("receipt index operation requires PostgreSQL")
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        conn.exec_driver_sql("SET LOCAL statement_timeout='5s'")
        return _describe(conn, schema, expected_database)


def _budget(conn, deadline, lock_timeout_ms):
    remaining = int((deadline - monotonic()) * 1000)
    if remaining < 1:
        raise TimeoutError("receipt index operation exceeded its time budget")
    for setting, milliseconds in (("statement_timeout", remaining), ("lock_timeout", min(lock_timeout_ms, remaining))):
        conn.execute(text("SELECT set_config(:setting,:value,false)"), dict(setting=setting, value=f"{milliseconds}ms"))


def apply_index(engine, *, expected_database, schema="public", timeout_ms=120000, lock_timeout_ms=5000, analyze=False):
    if not expected_database:
        raise ValueError("--expected-database is required for --apply")
    if (
        type(timeout_ms) is not int
        or not 1 <= timeout_ms <= 900000
        or type(lock_timeout_ms) is not int
        or not 1 <= lock_timeout_ms <= 60000
    ):
        raise ValueError("index time budgets must be positive and bounded")
    qualified(schema, TABLE_NAME)
    if engine.dialect.name != "postgresql":
        raise ValueError("receipt index operation requires PostgreSQL")
    before, backend_pid, created, analyzed = None, None, False, False
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            saved = {
                setting: conn.exec_driver_sql("SHOW " + setting).scalar_one()
                for setting in ("statement_timeout", "lock_timeout")
            }
            deadline = monotonic() + timeout_ms / 1000
            try:
                _budget(conn, deadline, lock_timeout_ms)
                before = _describe(conn, schema, expected_database)
                backend_pid = conn.exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
                if before["state"] not in {"missing", "ready"}:
                    return dict(
                        state="refused",
                        index=before,
                        create_completed=False,
                        analyzed=False,
                        reason="existing index requires explicit inspection; nothing dropped",
                    )
                if before["state"] == "missing":
                    _budget(conn, deadline, lock_timeout_ms)
                    conn.exec_driver_sql(create_statement(schema))
                    created = True
                if analyze:
                    _budget(conn, deadline, lock_timeout_ms)
                    conn.exec_driver_sql("ANALYZE " + qualified(schema, TABLE_NAME))
                    analyzed = True
                _budget(conn, deadline, lock_timeout_ms)
                after = _describe(conn, schema, expected_database)
                return dict(
                    state=after["state"],
                    index=after,
                    create_completed=created,
                    analyzed=analyzed,
                    backend_pid=backend_pid,
                )
            finally:
                try:
                    for setting, value in saved.items():
                        conn.execute(
                            text("SELECT set_config(:setting,:value,false)"), dict(setting=setting, value=value)
                        )
                except DBAPIError:
                    conn.invalidate()
    except (DBAPIError, TimeoutError) as exc:
        # Only observe after an uncertain concurrent build. OID presence does
        # not authorize dropping an object or retrying while another build runs.
        after = check_index(engine, schema=schema, expected_database=expected_database)
        return dict(
            state="failed",
            index=after,
            before=before,
            backend_pid=backend_pid,
            create_completed=created,
            analyzed=analyzed,
            sqlstate=getattr(getattr(exc, "orig", None), "pgcode", None),
            reason="bounded operation failed; inspect OID/definition and old snapshots; nothing dropped",
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--analyze", action="store_true")
    parser.add_argument("--schema", default="public")
    parser.add_argument("--expected-database")
    parser.add_argument("--timeout-ms", type=int, default=120000)
    parser.add_argument("--lock-timeout-ms", type=int, default=5000)
    args = parser.parse_args(argv)
    if args.analyze and not args.apply:
        parser.error("--analyze requires explicit --apply")
    if not os.environ.get("KATRAIN_DATABASE_URL"):
        parser.error("set KATRAIN_DATABASE_URL in the process environment")
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"], echo=False, hide_parameters=True, poolclass=NullPool)
    try:
        if args.apply:
            result = apply_index(
                engine,
                expected_database=args.expected_database,
                schema=args.schema,
                timeout_ms=args.timeout_ms,
                lock_timeout_ms=args.lock_timeout_ms,
                analyze=args.analyze,
            )
        else:
            index = check_index(engine, schema=args.schema, expected_database=args.expected_database)
            result = dict(state=index["state"], index=index)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["state"] == "ready" else 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
