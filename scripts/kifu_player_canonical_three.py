"""Capture, dry-run, or apply the frozen three-person exact player FK decision."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from katrain.web.kifu.player_canonical_three import capture, run  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
REVIEWS = {
    "test": ("e2e4599263d88cf931cf9e0ac454b1f46fe7353fbc11af918c82ff7d8f8d2092", "katrain_db"),
    "prod": ("49379c3cca58c3a65b732c7775c22a251d04455d589847f4a9ec03be58f59ef6", "katrain_prod_20260725"),
}


def load(path, expected_sha256):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError(f"pinned SHA differs: {path}")
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "dry", "apply"))
    parser.add_argument("--environment", choices=REVIEWS, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256")
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--database-url", default=os.getenv("KATRAIN_DATABASE_URL"))
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("database URL required")
    if args.command != "capture" and not args.plan_sha256:
        parser.error("dry/apply requires --plan-sha256")
    if args.command == "apply" and args.approved_plan_sha256 != args.plan_sha256:
        parser.error("apply requires separately approved plan SHA")
    expected_review_sha, database = REVIEWS[args.environment]
    review_path = ROOT / f"docs/resource/kifu-player-exact-canonical-three-frozen-review-{args.environment}-2026-10-04.json"
    review = load(review_path, expected_review_sha)
    engine = create_engine(args.database_url)
    try:
        if args.command == "capture":
            plan = capture(engine, review, args.environment, expected_review_sha)
            if plan["database"] != database:
                raise ValueError("database differs")
            raw = gzip.compress(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                           separators=(",", ":")).encode(), mtime=0)
            args.plan.write_bytes(raw)
            print(json.dumps({"plan_sha256": hashlib.sha256(raw).hexdigest(), "counts": plan["counts"]},
                             ensure_ascii=False, sort_keys=True))
        else:
            plan = load(args.plan, args.plan_sha256)
            if plan["database"] != database:
                raise ValueError("database differs")
            result = run(engine, review, args.environment, expected_review_sha, plan,
                         apply=args.command == "apply", plan_sha256=args.plan_sha256,
                         approved_plan_sha256=args.approved_plan_sha256)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
