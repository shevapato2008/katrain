"""Capture or transactionally dry-run the reviewed exact-slot links."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from katrain.web.kifu.catalog_player_exact import capture_exact_plan, run_exact_plan  # noqa: E402


def pinned(path, expected_sha):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError(f"file SHA-256 differs: {path}")
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "run"))
    parser.add_argument("--environment", choices=("test", "prod"), required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--review-sha256", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256")
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--database-url", default=os.getenv("KATRAIN_DATABASE_URL"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("database URL required")
    if args.command == "run" and not args.plan_sha256:
        parser.error("run requires --plan-sha256")
    if args.apply and args.command != "run":
        parser.error("--apply requires run")
    if args.apply and args.approved_plan_sha256 != args.plan_sha256:
        parser.error("--apply requires matching --approved-plan-sha256")
    inventory = pinned(args.inventory, args.inventory_sha256)
    review = pinned(args.review, args.review_sha256)
    engine = create_engine(args.database_url)
    try:
        if args.command == "capture":
            plan = capture_exact_plan(inventory, review, args.review_sha256, args.environment, engine)
            payload = gzip.compress(
                json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(), mtime=0
            )
            args.plan.write_bytes(payload)
            print(
                json.dumps(
                    {"plan_sha256": hashlib.sha256(payload).hexdigest(), "counts": plan["counts"]},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            plan = pinned(args.plan, args.plan_sha256)
            print(
                json.dumps(
                    run_exact_plan(
                        inventory,
                        review,
                        args.review_sha256,
                        args.environment,
                        plan,
                        engine,
                        apply=args.apply,
                        approved_plan_sha256=args.approved_plan_sha256,
                        plan_sha256=args.plan_sha256,
                    ),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
