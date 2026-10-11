"""Read-only counts of raw kifu player spellings and current ID coverage."""

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("KATRAIN_DATABASE_URL"))
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("database URL required")
    engine = create_engine(args.database_url)
    values = defaultdict(lambda: {"slots": 0, "unlinked": 0, "player_ids": set()})
    games = 0
    try:
        with Session(engine) as db:
            statement = select(KifuAlbum.player_black, KifuAlbum.black_player_id,
                               KifuAlbum.player_white, KifuAlbum.white_player_id)
            for black, black_id, white, white_id in db.execute(statement).yield_per(5000):
                games += 1
                for raw, player_id in ((black, black_id), (white, white_id)):
                    row = values[raw]
                    row["slots"] += 1
                    if player_id is None:
                        row["unlinked"] += 1
                    else:
                        row["player_ids"].add(player_id)
    finally:
        engine.dispose()
    print(json.dumps({"games": games, "raw_values": [
        {"raw": raw, "slots": row["slots"], "unlinked": row["unlinked"],
         "player_ids": sorted(row["player_ids"])}
        for raw, row in sorted(values.items(), key=lambda item: (-item[1]["unlinked"], str(item[0])))]},
        ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
