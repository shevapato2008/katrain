"""Explicit small-batch admission for professional kifu analysis.

Dry run by default. Full-corpus admission is intentionally unavailable.
"""

import argparse
import hashlib

from sqlalchemy.exc import IntegrityError

from katrain.cron.config import KATAGO_EXPECTED_MODEL_SHA256
from katrain.cron.db import SessionLocal
from katrain.cron.models import KifuAlbumDB, KifuAnalysisJobDB
from katrain.cron.sgf import parse_game


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("album_ids", nargs="+", type=int, help="At most 20 explicitly selected album IDs")
    parser.add_argument("--apply", action="store_true", help="Insert idempotent jobs")
    args = parser.parse_args()
    if not 1 <= len(args.album_ids) <= 20:
        parser.error("Select 1–20 album IDs per run")
    if not KATAGO_EXPECTED_MODEL_SHA256:
        parser.error("KATAGO_EXPECTED_MODEL_SHA256 must pin the deployed transformer")

    seen: set[int] = set()
    with SessionLocal() as db:
        for requested_id in args.album_ids:
            requested = db.query(KifuAlbumDB).filter(KifuAlbumDB.id == requested_id).first()
            if requested is None:
                print(f"{requested_id}: missing")
                continue
            canonical_id = requested.duplicate_of_id or requested.id
            canonical = db.query(KifuAlbumDB).filter(KifuAlbumDB.id == canonical_id).first()
            if canonical is None or canonical.duplicate_of_id is not None or canonical.sgf_content != requested.sgf_content:
                print(f"{requested_id}: invalid duplicate link or SGF changed")
                continue
            if canonical_id in seen:
                print(f"{requested_id}: already selected canonical {canonical_id}")
                continue
            seen.add(canonical_id)
            parsed = parse_game(canonical.sgf_content)
            if parsed.dropped_midgame_setup or parsed.invalid_moves or not parsed.moves:
                print(f"{requested_id}: unsupported SGF")
                continue
            sha = hashlib.sha256(canonical.sgf_content.encode("utf-8")).hexdigest()
            identity = dict(album_id=canonical_id, sgf_sha256=sha,
                            model_sha256=KATAGO_EXPECTED_MODEL_SHA256, requested_visits=2000)
            existing = db.query(KifuAnalysisJobDB).filter_by(**identity).first()
            if existing:
                print(f"{requested_id}: existing job {existing.id} ({existing.status})")
                continue
            print(f"{requested_id}: canonical {canonical_id}, {len(parsed.moves)} moves, 2000 visits, {'admitting' if args.apply else 'dry run'}")
            if args.apply:
                try:
                    db.add(KifuAnalysisJobDB(**identity, status="pending", total_moves=len(parsed.moves), analyzed_moves=0))
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    print(f"{requested_id}: concurrent admission already exists")


if __name__ == "__main__":
    main()
