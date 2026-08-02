#!/usr/bin/env python3
"""Read-only post-freeze termination audit for the HumanSL temperature pilot v2 evidence."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Mapping, Sequence

import run_temperature_pilot as runner


AUDIT_SCOPE = "humansl-temperature-pilot-v2-post-freeze-audit-v1"
FROZEN_V2_MANIFEST_SHA256 = "573bb59d0242c1916fef220d355849de1ef4afd665d4ab66ebfce40fd2be7f7a"
FROZEN_V2_MANIFEST_PATH = "superpowers/tracks/golaxy-ai-ladder-parity/calibration/temperature_pilot_v2.json"


@contextmanager
def _repository_cwd(root: Path):
    previous = Path.cwd()
    os.chdir(root)
    try:
        yield
    finally:
        os.chdir(previous)


def audit_validated_checkpoint_records(records: Sequence[Mapping[str, object]], matchup: Mapping[str, object]) -> dict:
    """Audit termination only after the frozen v2 runtime's strict validation has succeeded."""
    games = records[1:]
    target = matchup.get("target_complete_pairs")
    cap = matchup.get("max_pair_attempts")
    if type(target) is not int or target <= 0 or type(cap) is not int or cap <= 0:
        raise ValueError("post-freeze audit matchup limits are invalid")
    if len(games) > 2 * cap:
        raise ValueError("post-freeze audit checkpoint exceeds the pair-attempt cap")
    if len(games) % 2:
        raise ValueError("post-freeze audit checkpoint ends with a dangling half-pair")

    complete_pairs = 0
    terminal_attempt = None
    for offset in range(0, len(games), 2):
        pair = games[offset : offset + 2]
        attempt = offset // 2
        if any(row.get("pair_attempt") != attempt for row in pair):
            raise ValueError("post-freeze audit checkpoint pair order is invalid")
        if all(row.get("conclusive") is True for row in pair):
            complete_pairs += 1
            if complete_pairs == target:
                terminal_attempt = attempt
                if offset + 2 != len(games):
                    raise ValueError(f"post-freeze audit found rows after {target} complete pairs")

    if complete_pairs != target or terminal_attempt is None:
        raise ValueError(f"post-freeze audit expected exactly {target} complete pairs")
    return {
        "complete_pairs": complete_pairs,
        "pair_attempts": len(games) // 2,
        "terminal_pair_attempt": terminal_attempt,
    }


def audit_pilot(
    manifest_path: Path | str,
    results_dir: Path | str,
    *,
    repo_root: Path | str = runner.REPO_ROOT,
) -> dict:
    """Run the frozen strict gate first, then audit v2 termination without writing evidence."""
    root = Path(repo_root).resolve()
    frozen_manifest_path = root / FROZEN_V2_MANIFEST_PATH
    if Path(manifest_path).resolve() != frozen_manifest_path:
        raise ValueError("post-freeze audit requires the repository's frozen temperature pilot v2 manifest")
    results = Path(results_dir).resolve()
    snapshots = {
        path.name: path.read_bytes() for path in results.iterdir() if path.is_file() and not path.name.endswith(".lock")
    }

    # Frozen strict validation creates lock sidecars, so run it against a disposable byte-for-byte evidence snapshot.
    with tempfile.TemporaryDirectory(prefix="temperature-pilot-v2-post-freeze-audit-") as temporary_name:
        strict_results = Path(temporary_name)
        for name, snapshot in snapshots.items():
            (strict_results / name).write_bytes(snapshot)
        # The frozen fingerprint binds this repository-relative manifest spelling. Restore CWD on every exit path.
        with _repository_cwd(root), contextlib.redirect_stdout(io.StringIO()):
            frozen_gate = runner.check_pilot(FROZEN_V2_MANIFEST_PATH, strict_results, repo_root=root)
            _manifest, strict_evidence = runner._collect_evidence(
                FROZEN_V2_MANIFEST_PATH, strict_results, repo_root=root
            )

    manifest = runner.pilot.validate_manifest_file(frozen_manifest_path, root)
    if manifest.get("schema_version") != 2 or manifest.get("manifest_sha256") != FROZEN_V2_MANIFEST_SHA256:
        raise ValueError("post-freeze audit requires the exact frozen temperature pilot v2 manifest")

    selfplay = runner.run_selfplay
    strict_evidence_by_matchup = {row["matchup_id"]: row for row in strict_evidence}
    checkpoint_reports = []
    for matchup in manifest["matchups"]:
        path = runner.checkpoint_path(results, matchup)
        try:
            snapshot = snapshots[path.name]
            evidence = strict_evidence_by_matchup[matchup["matchup_id"]]
        except KeyError as exc:
            raise ValueError("post-freeze audit evidence snapshot is incomplete") from exc
        selfplay._validate_checkpoint_byte_bounds(snapshot)
        checkpoint_sha256 = hashlib.sha256(snapshot).hexdigest()
        if checkpoint_sha256 != evidence.get("checkpoint_sha256"):
            raise ValueError("checkpoint changed between frozen strict validation and post-freeze audit")
        records = selfplay._parse_strict_jsonl(snapshot, context="temperature pilot v2 post-freeze audit")
        termination = audit_validated_checkpoint_records(records, matchup)
        checkpoint_reports.append(
            {
                "matchup_id": matchup["matchup_id"],
                "checkpoint": str(path),
                "checkpoint_sha256": checkpoint_sha256,
                **termination,
            }
        )

    return {
        "schema_version": 1,
        "audit_scope": AUDIT_SCOPE,
        "audit_status": "pass",
        "relationship_to_frozen_gate": "supplemental read-only audit; the frozen v2 gate is unchanged",
        "manifest_sha256": manifest["manifest_sha256"],
        "frozen_gate": frozen_gate,
        "checkpoints": checkpoint_reports,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--results-dir", required=True, type=Path)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    report = audit_pilot(args.manifest, args.results_dir)
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
