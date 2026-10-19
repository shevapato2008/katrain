"""Read exact album/event preimages for a reviewed list of IDs."""

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum, KifuEvent, KifuEventEdition


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", required=True, help="comma-separated album IDs")
    parser.add_argument("--database-url", default=os.getenv("KATRAIN_DATABASE_URL"))
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("database URL required")
    ids = [int(value) for value in args.ids.split(",")]
    if not ids or len(ids) != len(set(ids)):
        parser.error("empty or duplicate album IDs")
    engine = create_engine(args.database_url)
    try:
        with Session(engine) as db:
            total = db.scalar(select(func.count()).select_from(KifuAlbum))
            rows = db.execute(
                select(KifuAlbum.id, KifuAlbum.event, KifuAlbum.date_played,
                       KifuAlbum.event_id, KifuAlbum.event_edition_id,
                       KifuEvent.canonical_name, KifuEventEdition.edition_number,
                       KifuEventEdition.year)
                .outerjoin(KifuEvent, KifuAlbum.event_id == KifuEvent.id)
                .outerjoin(KifuEventEdition, KifuAlbum.event_edition_id == KifuEventEdition.id)
                .where(KifuAlbum.id.in_(ids))
            ).all()
            if len(rows) != len(ids):
                raise ValueError("missing album IDs")
            records = [dict(zip(("album_id", "raw_event", "date_played", "event_id",
                                 "event_edition_id", "event_name", "edition_number",
                                 "edition_year"), row)) for row in rows]
            print(json.dumps({"expected_total_albums": total,
                              "rows": sorted(records, key=lambda row: row["album_id"])},
                             ensure_ascii=False, indent=2))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
