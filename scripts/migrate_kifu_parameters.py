"""Add only the two nullable professional-analysis verification columns.

KATRAIN_DATABASE_URL selects the database. Dry-run by default; --apply performs
transactional, idempotent ADD COLUMN. Stop old cron workers before applying and
deploy the new worker/API together. Existing rows stay NULL/unverified: never
backfill proof or hashes onto results produced by the old defaulting worker.
The web startup add_missing_columns migration also supports these model columns.
"""

import argparse
import os

from sqlalchemy import create_engine, inspect, text


COLUMNS = (
    ("kifu_analysis_jobs", "analysis_parameters", "JSON"),
    ("kifu_analysis_moves", "parameter_sha256", "VARCHAR(64)"),
)


def migrate(engine, *, apply=False):
    if engine.dialect.name not in {"sqlite", "postgresql"}:
        raise ValueError("Only PostgreSQL and SQLite are supported")
    statements = []
    with engine.begin() as conn:
        if apply and engine.dialect.name == "postgresql":
            conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            conn.execute(text("SET LOCAL statement_timeout = '30s'"))
            # Inspect under the same lock, so concurrent app startup/migrations
            # cannot race this small ADD COLUMN migration.
            conn.execute(text("LOCK TABLE kifu_analysis_jobs, kifu_analysis_moves IN ACCESS EXCLUSIVE MODE"))
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        for table, column, sql_type in COLUMNS:
            if table not in tables:
                raise ValueError(f"Missing {table}; initialize the existing kifu schema first")
            if column not in {c["name"] for c in inspector.get_columns(table)}:
                statements.append(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {sql_type}')
        if apply:
            for statement in statements:
                conn.execute(text(statement))
    return statements


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    url = os.environ.get("KATRAIN_DATABASE_URL")
    if not url:
        parser.error("Set KATRAIN_DATABASE_URL in the process environment")
    engine = create_engine(url, echo=False, hide_parameters=True)
    try:
        statements = migrate(engine, apply=args.apply)
        for statement in statements:
            print(statement + ";")
        print(f"{'Applied' if args.apply else 'Dry run'}: {len(statements)} column(s); no data backfill")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
