"""Capture and dry-run the next 15 exact Chinese player raws; apply requires a reviewed plan hash."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from katrain.web.kifu.player_next15 import capture, run  # noqa: E402


DECISION = Path(__file__).resolve().parents[1] / "docs/resource/kifu-player-next15-independent-decision-astra-2026-10-04.json"
DECISION_SHA256 = "a3f3f0661de87d949216bd23269016c2e920d1540ae466392a1ce23b88726560"
INVENTORIES = {
    "test": ("08007a829412fc585888cbbcadd2e0d1e2fd0080af3017f4a85019170689e52b", "katrain_db"),
    "prod": ("dcc4f547ec196bbe850b79b6ce11a97dfda64e92343fcb2640dbd1aebaaad743", "katrain_prod_20260725"),
}


def load(path, expected_hash):
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_hash:
        raise ValueError(f"pinned file SHA differs: {path}")
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "dry", "apply"))
    parser.add_argument("--environment", choices=("test", "prod"), required=True)
    parser.add_argument("--inventory", type=Path, required=True)
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
    expected_inventory_sha, database = INVENTORIES[args.environment]
    inventory = load(args.inventory, expected_inventory_sha)
    decision_bytes = DECISION.read_bytes()
    review_sha = hashlib.sha256(decision_bytes).hexdigest()
    if review_sha != DECISION_SHA256:
        raise ValueError("identity decision SHA differs")
    decision = json.loads(decision_bytes)
    if decision["inputs"]["inventories"][args.environment.upper()]["file_sha256"] != expected_inventory_sha:
        raise ValueError("decision inventory pin differs")
    engine = create_engine(args.database_url)
    try:
        with engine.connect() as conn:
            actual = conn.scalar(text("SELECT current_database()"))
            if actual != database:
                raise ValueError(f"database differs: expected {database}, got {actual}")
        if args.command == "capture":
            plan = capture(engine, inventory, decision, args.environment, review_sha)
            if plan["database"] != database:
                raise ValueError("captured database differs")
            raw = gzip.compress(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                           separators=(",", ":")).encode(), mtime=0)
            args.plan.write_bytes(raw)
            print(json.dumps({"plan_sha256": hashlib.sha256(raw).hexdigest(), "counts": plan["counts"]},
                             ensure_ascii=False, sort_keys=True))
        else:
            plan = load(args.plan, args.plan_sha256)
            if plan["database"] != database:
                raise ValueError("plan database differs")
            result = run(engine, inventory, decision, args.environment, review_sha, plan,
                         apply=args.command == "apply", plan_sha256=args.plan_sha256,
                         approved_plan_sha256=args.approved_plan_sha256)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
