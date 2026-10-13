"""Check or apply a reviewed, frozen kifu event plan."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine

from scripts.import_kifu_event_types import run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args(argv)
    raw = args.plan.read_bytes()
    plan = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    if plan.get("version") != 1:
        raise ValueError("unsupported frozen event plan version")
    engine = create_engine(args.database_url)
    try:
        report = run(engine, plan, apply=args.apply, approved_sha256=args.approved_plan_sha256)
    finally:
        engine.dispose()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
