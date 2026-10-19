"""Capture, dry-run, or apply the 6,810 independently reviewed league event links."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from katrain.web.kifu.event_leagues_exact import DATABASES, capture, run  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "dry", "apply"))
    parser.add_argument("--environment", choices=DATABASES, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256")
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--database-url", default=os.getenv("KATRAIN_DATABASE_URL"))
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("database URL required")
    if args.command != "capture" and not args.plan_sha256:
        parser.error("dry/apply requires --plan-sha256")
    engine = create_engine(args.database_url)
    try:
        if args.command == "capture":
            plan = capture(engine, args.environment)
            data = gzip.compress(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                            separators=(",", ":")).encode(), mtime=0)
            args.plan.write_bytes(data)
            print(json.dumps({"plan_sha256": hashlib.sha256(data).hexdigest(), "counts": plan["counts"]}))
        else:
            data = args.plan.read_bytes()
            if hashlib.sha256(data).hexdigest() != args.plan_sha256:
                raise ValueError("plan byte SHA differs")
            plan = json.loads(gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data)
            result = run(engine, args.environment, plan, apply=args.command == "apply",
                         plan_sha256=args.plan_sha256, approved_plan_sha256=args.approved_plan_sha256)
            print(json.dumps(result, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
