"""Sync reviewed page links after name batches. Run migrate_kifu_player_pages.sql first.

Use dry-run for a read-only preview; apply only updates authoritative_pages.
Omit --player-id to backfill all eligible existing players.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine

from katrain.web.kifu.player_pages import sync_player_pages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("dry-run", "apply"))
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--player-id", action="append", type=int)
    args = parser.parse_args(argv)
    engine = create_engine(args.database_url)
    try:
        report = sync_player_pages(engine, player_ids=args.player_id, apply=args.command == "apply")
    finally:
        engine.dispose()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
