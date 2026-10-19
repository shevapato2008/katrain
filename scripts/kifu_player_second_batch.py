"""Capture and dry-run the reviewed second player batch; --apply commits it.

All input files and the captured plan require explicit SHA-256 pins. The
reviewed v2 file is the only source of exact raw spellings and person targets.
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

from katrain.web.kifu.catalog_player_second import capture_second_plan, run_second_plan  # noqa: E402


def read_pinned(path, sha256):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError(f"file SHA-256 mismatch: {path}")
    return json.loads(gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "run"))
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--original-catalog", required=True, type=Path)
    parser.add_argument("--original-catalog-sha256", required=True)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--review-sha256", required=True)
    parser.add_argument("--plan", required=True, type=Path)
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
    catalog = read_pinned(args.original_catalog, args.original_catalog_sha256)
    review = read_pinned(args.review, args.review_sha256)
    if review["input"]["inventory_sha256"] != args.inventory_sha256:
        raise ValueError("review was made from a different frozen inventory file")
    if review["input"]["catalog_sha256"] != args.original_catalog_sha256:
        raise ValueError("review was made from a different original catalog file")
    engine = create_engine(url)
    try:
        if args.command == "capture":
            plan = capture_second_plan(inventory, review, catalog, args.review_sha256, engine)
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
            result = run_second_plan(inventory, review, catalog, args.review_sha256, plan, engine,
                                     apply=args.apply)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
