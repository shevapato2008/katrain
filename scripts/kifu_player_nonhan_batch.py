"""Capture or transactionally preview a reviewed exact Latin player allowlist.

Capture and run require pinned source, frozen inventory, and plan SHA-256 files.
Run rolls back by default. TEST and PROD use separate target IDs and plans.
"""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from katrain.web.kifu.catalog_player_nonhan import capture_nonhan_plan, run_nonhan_plan  # noqa: E402


def read_pinned(path, sha256):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError(f"file SHA-256 mismatch: {path}")
    return json.loads(gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "run"))
    parser.add_argument("--environment", choices=("test", "prod"), required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--allowlist", type=Path, required=True)
    parser.add_argument("--allowlist-sha256", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256")
    parser.add_argument("--database-url", help="defaults to KATRAIN_DATABASE_URL")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and args.command != "run":
        parser.error("--apply is valid only for run")
    if args.command == "run" and not args.plan_sha256:
        parser.error("run requires --plan-sha256")
    url = args.database_url or os.getenv("KATRAIN_DATABASE_URL")
    if not url:
        parser.error("database URL required")
    inventory = read_pinned(args.inventory, args.inventory_sha256)
    allowlist = read_pinned(args.allowlist, args.allowlist_sha256)
    engine = create_engine(url)
    try:
        if args.command == "capture":
            plan = capture_nonhan_plan(inventory, allowlist, args.allowlist_sha256, args.environment, engine)
            payload = gzip.compress(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                               separators=(",", ":")).encode("utf-8"), mtime=0)
            args.plan.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.plan.with_name(args.plan.name + ".tmp")
            try:
                temporary.write_bytes(payload)
                os.replace(temporary, args.plan)
            finally:
                temporary.unlink(missing_ok=True)
            print(json.dumps({"plan_sha256": hashlib.sha256(payload).hexdigest(),
                              "counts": plan["counts"]}, ensure_ascii=False, sort_keys=True))
        else:
            plan = read_pinned(args.plan, args.plan_sha256)
            print(json.dumps(run_nonhan_plan(inventory, allowlist, args.allowlist_sha256,
                                            args.environment, plan, engine, apply=args.apply),
                             ensure_ascii=False, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
