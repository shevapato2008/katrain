"""Validate, preview, apply and conditionally undo reviewed kifu-name bundles.

No command creates a catalog schema. Run the explicit catalog migration first.
`apply` and `undo` write only the database URL supplied to this invocation.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine

from katrain.web.kifu.name_batch import (
    BatchError, apply_bundle, batch_status, dry_run_bundle, undo_batch,
)
from katrain.web.kifu.name_candidates import CandidateError, validate_bundle
from katrain.web.kifu.name_evidence import EvidenceError, load_registry


def _json(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def _jsonl(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise BatchError(f"{path}:{line_number}: invalid research JSON") from exc
                if not isinstance(row, dict):
                    raise BatchError(f"{path}:{line_number}: research row must be an object")
                yield row


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "dry-run", "apply"):
        sub = commands.add_parser(command)
        sub.add_argument("--bundle", type=Path, required=True)
        sub.add_argument("--registry", type=Path, required=True)
        sub.add_argument("--inventory", type=Path, required=True)
        sub.add_argument("--evidence", type=Path, required=True)
        if command != "validate":
            sub.add_argument("--database-url", required=True)
    for command in ("status", "undo"):
        sub = commands.add_parser(command)
        sub.add_argument("--database-url", required=True)
        sub.add_argument("--batch-id", type=int, required=True)
    args = parser.parse_args(argv)
    engine = None
    try:
        if args.command in {"validate", "dry-run", "apply"}:
            registry = load_registry(args.registry)
            inventory = _json(args.inventory)
            bundle = _json(args.bundle)
            evidence_records = list(_jsonl(args.evidence))
            if args.command == "validate":
                result = validate_bundle(bundle, registry, inventory, evidence_records)
            else:
                engine = create_engine(args.database_url)
                result = (dry_run_bundle if args.command == "dry-run" else apply_bundle)(
                    engine, bundle, registry, inventory, evidence_records)
        else:
            engine = create_engine(args.database_url)
            result = batch_status(engine, args.batch_id) if args.command == "status" else undo_batch(engine, args.batch_id)
    except (BatchError, CandidateError, EvidenceError, OSError, json.JSONDecodeError) as exc:
        result = {"ready": False, "error": str(exc)}
    finally:
        if engine is not None:
            engine.dispose()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ready", True) and "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
