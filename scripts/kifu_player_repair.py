"""Capture and repair only reviewed false-person player raw values.

Capture is read-only. Run defaults to transactional dry-run; --apply commits
the same preimage-checked edits.
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

from katrain.web.kifu.catalog_player_repair import capture_repair_plan, run_repair_plan  # noqa: E402


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
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--batch-sha256", required=True)
    parser.add_argument("--exclusions", type=Path)
    parser.add_argument("--exclusions-sha256")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--plan-sha256")
    parser.add_argument("--database-url", help="defaults to KATRAIN_DATABASE_URL")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and args.command != "run":
        parser.error("--apply is valid only for run")
    if args.command == "capture" and not (args.exclusions and args.exclusions_sha256 and args.plan):
        parser.error("capture requires pinned --exclusions and --plan output")
    if args.command == "run" and not (args.plan and args.plan_sha256):
        parser.error("run requires pinned --plan and --plan-sha256")
    url = args.database_url or os.getenv("KATRAIN_DATABASE_URL")
    if not url:
        parser.error("database URL required")
    inventory = read_pinned(args.inventory, args.inventory_sha256)
    batch = read_pinned(args.batch, args.batch_sha256)
    engine = create_engine(url)
    try:
        if args.command == "capture":
            exclusion_data = read_pinned(args.exclusions, args.exclusions_sha256)
            plan = capture_repair_plan(inventory, batch, exclusion_data["rows"], engine)
            payload = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            args.plan.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.plan.with_name(args.plan.name + ".tmp")
            try:
                temporary.write_bytes(payload)
                os.replace(temporary, args.plan)
            finally:
                temporary.unlink(missing_ok=True)
            print(json.dumps({"plan_sha256": hashlib.sha256(payload).hexdigest(),
                              "counts": plan["counts"]}, sort_keys=True))
        else:
            plan = read_pinned(args.plan, args.plan_sha256)
            print(json.dumps(run_repair_plan(inventory, batch, plan, engine, apply=args.apply),
                             ensure_ascii=False, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
