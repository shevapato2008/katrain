#!/usr/bin/env python3
"""Explicit additive media-task migration. Never imported/run at app startup.

Run against the intended, backed-up test database:
    DATABASE_URL=... python scripts/migrate_tutorial_media.py --apply
No tutorial content or existing table is altered.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, inspect
from katrain.web.core.models_db import TutorialMediaTask


def migrate(connection):
    table = TutorialMediaTask.__table__
    table.create(connection, checkfirst=True)
    actual = {column["name"] for column in inspect(connection).get_columns(table.name)}
    missing = set(table.columns.keys()) - actual
    if missing:
        raise RuntimeError(f"Media task table schema is incomplete: {sorted(missing)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", required=True)
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        parser.error("DATABASE_URL must explicitly identify the intended test database")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            migrate(connection)
        print("tutorial_media_tasks migration complete")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
