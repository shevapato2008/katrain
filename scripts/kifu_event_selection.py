"""Validate, preview, apply, inspect or undo reviewed per-album event selections.

The schema must be migrated separately. ``validate`` needs no database;
``dry-run`` only reads; ``apply`` needs the full bundle SHA-256 from the
independent review record; ``apply`` and ``undo`` target the supplied database.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine

from katrain.web.kifu.event_selection import (
    EventSelectionError,
    apply_bundle,
    batch_status,
    dry_run_bundle,
    undo_batch,
    validate_bundle,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "dry-run", "apply"):
        sub = commands.add_parser(command)
        sub.add_argument("--bundle", type=Path, required=True)
        if command != "validate":
            sub.add_argument("--database-url", required=True)
        if command == "apply":
            sub.add_argument("--approved-bundle-sha256", required=True)
    for command in ("status", "undo"):
        sub = commands.add_parser(command)
        sub.add_argument("--database-url", required=True)
        sub.add_argument("--batch-id", type=int, required=True)
    args = parser.parse_args(argv)
    engine = None
    try:
        if args.command in {"validate", "dry-run", "apply"}:
            bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
            if args.command == "validate":
                result = validate_bundle(bundle)
            else:
                engine = create_engine(args.database_url)
                if args.command == "dry-run":
                    result = dry_run_bundle(engine, bundle)
                else:
                    result = apply_bundle(engine, bundle, expected_bundle_sha256=args.approved_bundle_sha256)
        else:
            engine = create_engine(args.database_url)
            result = (batch_status if args.command == "status" else undo_batch)(engine, args.batch_id)
    except (EventSelectionError, OSError, json.JSONDecodeError) as exc:
        result = {"ready": False, "error": str(exc)}
    finally:
        if engine is not None:
            engine.dispose()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ready", True) and "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
