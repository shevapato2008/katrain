"""Check, rollback-test, apply, verify or undo one pinned duplicate-player merge."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from katrain.web.kifu.player_duplicate import check, run, undo, verify  # noqa: E402
from scripts.kifu_player_duplicate_proposal import native_duplicate_columns  # noqa: E402


def _load(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "dry-run", "apply", "verify", "undo"))
    parser.add_argument("--database-url", default=os.getenv("KATRAIN_DATABASE_URL"))
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--preimage", type=Path)
    parser.add_argument("--plan-sha256", help="canonical JSON SHA-256 of the unchanged pending proposal")
    parser.add_argument("--review", type=Path, help="independent-approved review JSON; required for apply")
    parser.add_argument("--review-file-sha256", help="SHA-256 of exact review file bytes; required for apply")
    parser.add_argument("--actor-id", help="actual applying actor; required for apply")
    parser.add_argument("--batch-id", type=int)
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("database URL required")
    if args.command in {"check", "dry-run", "apply"}:
        if not args.plan or not args.preimage or not args.plan_sha256:
            parser.error("check/dry-run/apply requires --plan, --preimage and --plan-sha256")
        plan, preimage = _load(args.plan), _load(args.preimage)
        # The existing packet signs both the decompressed canonical preimage and
        # its exact compressed bytes. Both bindings must hold at the CLI boundary.
        if hashlib.sha256(args.preimage.read_bytes()).hexdigest() != plan.get("full_preimage_artifact", {}).get(
            "sha256"
        ):
            parser.error("preimage file bytes SHA mismatch")
    elif args.batch_id is None or args.batch_id <= 0:
        parser.error("verify/undo requires a positive --batch-id")
    if args.command == "apply" and not (args.review and args.review_file_sha256 and args.actor_id):
        parser.error("apply requires --review, --review-file-sha256 and --actor-id")
    review = None
    if args.review:
        if (
            not args.review_file_sha256
            or hashlib.sha256(args.review.read_bytes()).hexdigest() != args.review_file_sha256
        ):
            parser.error("review file bytes SHA mismatch")
        review = _load(args.review)
    engine = create_engine(args.database_url)
    try:
        native_duplicate_columns(engine, require_read_only=False)
        if args.command == "check":
            result = check(engine, plan, preimage, expected_plan_sha256=args.plan_sha256)
        elif args.command in {"dry-run", "apply"}:
            result = run(
                engine,
                plan,
                preimage,
                command=args.command,
                expected_plan_sha256=args.plan_sha256,
                review=review,
                actor_id=args.actor_id,
            )
        elif args.command == "verify":
            result = verify(engine, args.batch_id)
        else:
            result = undo(engine, args.batch_id)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return result
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
