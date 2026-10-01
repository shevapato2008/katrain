"""Capture and validate pending kifu-name research JSON Lines.

`capture` reads one task per line with owner, lang, source_id, query, URL and
optional candidate_name/identity_basis. It writes page checks, never approved
names or negative source-scope conclusions. Researchers assemble per-owner
records from those checks; `validate` checks the records before independent
language review and a separate database import.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from pathlib import Path

from katrain.web.kifu.name_evidence import (
    DEFAULT_REGISTRY,
    EvidenceError,
    capture_source_check,
    load_registry,
    product_language_tag,
    registry_sha256,
    validate_research_record,
)


def _rows(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EvidenceError(f"{path}:{line_number}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise EvidenceError(f"{path}:{line_number}: expected JSON object")
            yield line_number, row


def _atomic_jsonl(output: Path, rows):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, prefix=".kifu-research-",
                                         suffix=".jsonl", delete=False) as stream:
            temporary = Path(stream.name)
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _capture_rows(input_path: Path, registry: dict, *, min_interval: float, max_attempts: int):
    previous_started = None
    for line_number, task in _rows(input_path):
        owner = task.get("owner")
        if not isinstance(owner, dict) or set(owner) != {"kind", "id"} or owner["kind"] not in {
            "player", "event", "raw_player", "raw_event"
        } or type(owner["id"]) is not int or owner["id"] <= 0:
            raise EvidenceError(f"{input_path}:{line_number}: exact owner kind/id required")
        product_language_tag(task.get("lang"), registry)
        now = time.monotonic()
        if previous_started is not None:
            time.sleep(max(0.0, min_interval - (now - previous_started)))
        previous_started = time.monotonic()
        check = capture_source_check(task, registry, max_attempts=max_attempts)
        yield {"owner": owner, "lang": task["lang"], "source_check": check,
               "review_status": "pending", "registry_version": registry["version"],
               "registry_sha256": registry_sha256(registry)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("capture", "validate"):
        sub = commands.add_parser(command)
        sub.add_argument("--input", required=True, type=Path)
        sub.add_argument("--output", required=True, type=Path)
        if command == "capture":
            sub.add_argument("--min-interval", type=float, default=1.0)
            sub.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args(argv)
    registry = load_registry(args.registry)
    if args.command == "validate":
        rows = (validate_research_record(row, registry) for _, row in _rows(args.input))
    else:
        if args.min_interval < 0 or args.max_attempts < 1:
            parser.error("capture limits must be nonnegative and attempts at least one")
        rows = _capture_rows(args.input, registry, min_interval=args.min_interval,
                             max_attempts=args.max_attempts)
    _atomic_jsonl(args.output, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
