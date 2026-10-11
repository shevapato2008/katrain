"""Build or run a pinned, provisional Chinese player-ID and album-link batch.

Build needs OpenCC (`pip install opencc-python-reimplemented`). Run needs the
same frozen inventory and a fresh, environment-specific catalog snapshot.
Default run mode is a full transactional dry-run that rolls back all writes.
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

from katrain.web.kifu.catalog_player_auto import build_safe_chinese_batch, run_safe_chinese_batch  # noqa: E402


def _read(path, expected_sha):
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha != digest:
        raise ValueError(f"pinned file SHA-256 mismatch: {path}")
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return json.loads(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="build deterministic offline batch and full review queue")
    build.add_argument("--inventory", required=True, type=Path)
    build.add_argument("--inventory-sha256", required=True)
    build.add_argument("--catalog", required=True, type=Path)
    build.add_argument("--catalog-sha256", required=True)
    build.add_argument("--exclusions", required=True, type=Path,
                       help="reviewed exact raw values excluded from automatic person IDs")
    build.add_argument("--exclusions-sha256", required=True)
    build.add_argument("--output", required=True, type=Path)
    run = sub.add_parser("run", help="check live preimages, then dry-run or apply in one transaction")
    run.add_argument("--inventory", required=True, type=Path)
    run.add_argument("--inventory-sha256", required=True)
    run.add_argument("--batch", required=True, type=Path)
    run.add_argument("--batch-sha256", required=True)
    run.add_argument("--database-url", help="defaults to KATRAIN_DATABASE_URL")
    run.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    inventory = _read(args.inventory, args.inventory_sha256)
    if args.command == "build":
        from opencc import OpenCC

        catalog = _read(args.catalog, args.catalog_sha256)
        exclusions = _read(args.exclusions, args.exclusions_sha256)
        excluded_raw_values = {row["raw_value"] for row in exclusions["rows"]}
        if len(excluded_raw_values) != exclusions["counts"]["raw_values"]:
            raise ValueError("reviewed exclusions contain duplicate raw spellings")
        batch = build_safe_chinese_batch(inventory, catalog, OpenCC("t2s").convert,
                                         excluded_raw_values)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(batch, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        temporary = args.output.with_name(args.output.name + ".tmp")
        try:
            temporary.write_bytes(payload)
            os.replace(temporary, args.output)
        finally:
            temporary.unlink(missing_ok=True)
        print(json.dumps({"batch_sha256": hashlib.sha256(payload).hexdigest(),
                          "counts": batch["counts"]}, ensure_ascii=False, sort_keys=True))
        return
    batch = _read(args.batch, args.batch_sha256)
    database_url = args.database_url or os.getenv("KATRAIN_DATABASE_URL")
    if not database_url:
        parser.error("run requires --database-url or KATRAIN_DATABASE_URL")
    engine = create_engine(database_url)
    try:
        report = run_safe_chinese_batch(inventory, batch, engine, apply=args.apply)
    finally:
        engine.dispose()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
