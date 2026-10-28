#!/usr/bin/env python3
"""Explicit prepared-search administration; migrate defaults to dry-run."""

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from katrain.web.core.config import settings
from katrain.web.kifu.prepared_migration import apply_migration, migration_plan, verify_schema


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=settings.DATABASE_URL)
    sub = parser.add_subparsers(dest="command", required=True)
    migrate = sub.add_parser("migrate")
    mode = migrate.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    sub.add_parser("verify-schema")
    args = parser.parse_args(argv)
    engine = create_engine(args.database_url, pool_pre_ping=True)
    try:
        if args.command == "migrate":
            result = apply_migration(engine) if args.apply else migration_plan(engine)
        else:
            result = verify_schema(engine)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0 if result.get("ok", not result.get("missing_inputs")) else 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
