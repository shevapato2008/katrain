#!/usr/bin/env python3
"""Explicit PostgreSQL search-index check/apply; never called by Web startup.

Run from the repository root: python -m scripts.kifu_search_indexes --check
Only --apply executes DDL. Invalid indexes are reported, never dropped/rebuilt.
"""

import argparse
import json

from sqlalchemy import create_engine

from katrain.web.core.config import settings
from katrain.web.core.migrations import apply_kifu_search_indexes, check_kifu_search_indexes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="read definitions/valid/ready and print the DDL plan")
    mode.add_argument("--apply", action="store_true", help="explicitly build each missing index concurrently")
    parser.add_argument("--timeout-ms", type=int, default=900_000, help="total apply time budget (default 15 minutes)")
    parser.add_argument("--lock-timeout-ms", type=int, default=10_000)
    args = parser.parse_args()
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        if args.apply:
            status = apply_kifu_search_indexes(engine, timeout_ms=args.timeout_ms, lock_timeout_ms=args.lock_timeout_ms)
            statements = []
        else:
            status, statements = check_kifu_search_indexes(engine)
        print(json.dumps({"indexes": status, "missing_index_plan": statements}, indent=2, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
