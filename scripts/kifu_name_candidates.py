"""Validate a finite reviewed kifu-name bundle without database writes.

Exit 0 only when every declared member has an independently approved decision.
The report does not claim that the declared members cover the entire catalog.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from katrain.web.kifu.name_candidates import CandidateError, validate_bundle
from katrain.web.kifu.name_evidence import EvidenceError, load_registry


def _read_json(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def _read_jsonl(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CandidateError(f"{path}:{number}: invalid JSON") from exc
            if not isinstance(value, dict):
                raise CandidateError(f"{path}:{number}: expected research object")
            yield value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--registry", required=True, type=Path)
    validate.add_argument("--inventory", required=True, type=Path)
    validate.add_argument("--bundle", required=True, type=Path)
    validate.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        registry = load_registry(args.registry)
        report = validate_bundle(_read_json(args.bundle), registry, _read_json(args.inventory),
                                 list(_read_jsonl(args.evidence)))
    except (CandidateError, EvidenceError, OSError, json.JSONDecodeError) as exc:
        report = {"ready": False, "approved": 0, "pending": 0, "rejected": 0, "missing": 0,
                  "errors": [str(exc)]}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
