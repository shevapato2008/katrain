"""Capture read-only, dry-run with rollback, or apply the pinned existing3 plan."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from katrain.web.kifu.player_existing3_exact import DATABASES, capture, encoded, run  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "dry", "apply"))
    parser.add_argument("--environment", choices=DATABASES, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--review-sha256", required=True)
    parser.add_argument("--review", type=Path, help="independent review artifact; required for apply")
    parser.add_argument("--plan-sha256")
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--database-url", default=os.getenv("KATRAIN_DATABASE_URL"))
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("database URL required")
    if args.command != "capture" and not args.plan_sha256:
        parser.error("dry/apply requires --plan-sha256")
    if args.command == "apply" and args.review is None:
        parser.error("apply requires --review independent decision artifact")
    if args.review is not None and hashlib.sha256(args.review.read_bytes()).hexdigest() != args.review_sha256:
        parser.error("independent review file SHA mismatch")
    engine = create_engine(args.database_url)
    try:
        if args.command == "capture":
            plan = capture(engine, args.environment, args.review_sha256)
            raw = gzip.compress(encoded(plan), mtime=0)
            args.plan.write_bytes(raw)
            print(json.dumps({"plan_sha256": hashlib.sha256(raw).hexdigest(), "slots": 407}))
        else:
            raw = args.plan.read_bytes()
            if hashlib.sha256(raw).hexdigest() != args.plan_sha256:
                raise ValueError("plan file SHA mismatch")
            plan = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
            if plan["review_sha256"] != args.review_sha256:
                raise ValueError("review decision SHA mismatch")
            print(
                json.dumps(
                    run(
                        engine,
                        args.environment,
                        plan,
                        apply=args.command == "apply",
                        plan_sha256=args.plan_sha256,
                        approved_plan_sha256=args.approved_plan_sha256,
                    )
                )
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
