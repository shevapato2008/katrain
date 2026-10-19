#!/usr/bin/env python3
"""Explicit additive nullable review columns; no approvals or history are backfilled.

Back up the intended test DB first, then:
    DATABASE_URL=... python scripts/migrate_tutorial_reviews.py --apply
Restore the pre-migration backup to roll back. This script never runs at startup.
"""

import argparse
import os

from sqlalchemy import create_engine, inspect, text

REVIEW_COLUMNS = ("board_review", "video_2d_review", "video_3d_review")


def migrate(connection):
    columns = {column["name"] for column in inspect(connection).get_columns("tutorial_figures")}
    for name in REVIEW_COLUMNS:
        if name not in columns:
            connection.execute(text(f'ALTER TABLE tutorial_figures ADD COLUMN "{name}" JSON NULL'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", required=True)
    parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        parser.error("DATABASE_URL must explicitly identify the intended, backed-up test database")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            migrate(connection)
        print("Nullable tutorial review columns added; no approvals created")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
