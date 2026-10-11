"""Roll back a reviewed exact set of incorrect kifu event links."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum, KifuEvent


def plan_sha256(plan: dict) -> str:
    return hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def run(engine, plan: dict, *, apply: bool, approved_plan_sha256: str | None = None) -> dict:
    sha256 = plan_sha256(plan)
    if apply and approved_plan_sha256 != sha256:
        raise ValueError("approved plan SHA-256 differs from exact plan")
    rows = plan["rows"]
    if not rows or len({row["album_id"] for row in rows}) != len(rows):
        raise ValueError("empty or duplicate rollback album IDs")
    with Session(engine) as db:
        with db.begin():
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums IN SHARE ROW EXCLUSIVE MODE"))
            if db.scalar(select(func.count()).select_from(KifuAlbum)) != plan["expected_total_albums"]:
                raise ValueError("live album count differs from rollback plan")
            names = dict(db.execute(select(KifuEvent.id, KifuEvent.canonical_name)
                                    .where(KifuEvent.id.in_({row["event_id"] for row in rows}))).all())
            actual = {album.id: album for album in db.execute(select(KifuAlbum)
                      .where(KifuAlbum.id.in_([row["album_id"] for row in rows]))).scalars()}
            if len(actual) != len(rows):
                raise ValueError("rollback preimage has missing album")
            for row in rows:
                album = actual[row["album_id"]]
                observed = (album.event, album.date_played, album.event_id, album.event_edition_id,
                            names.get(album.event_id))
                expected = (row["raw_event"], row["date_played"], row["event_id"],
                            row["event_edition_id"], row["event_name"])
                if observed != expected:
                    raise ValueError(f"rollback preimage mismatch for album {album.id}")
            report = {"plan_sha256": sha256, "matched_albums": len(rows),
                      "database_mode": "apply" if apply else "dry_run"}
            if not apply:
                return report
            for row in rows:
                result = db.execute(update(KifuAlbum).where(
                    KifuAlbum.id == row["album_id"], KifuAlbum.event == row["raw_event"],
                    KifuAlbum.date_played == row["date_played"],
                    KifuAlbum.event_id == row["event_id"],
                    KifuAlbum.event_edition_id == row["event_edition_id"],
                ).values(event_id=row["event_id"] if row.get("retain_event_type") else None,
                         event_edition_id=None))
                if result.rowcount != 1:
                    raise ValueError(f"rollback album {row['album_id']} changed during apply")
            report["updated_albums"] = len(rows)
            return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--database-url", default=os.getenv("KATRAIN_DATABASE_URL"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("database URL required")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    engine = create_engine(args.database_url)
    try:
        result = run(engine, plan, apply=args.apply, approved_plan_sha256=args.approved_plan_sha256)
    finally:
        engine.dispose()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
