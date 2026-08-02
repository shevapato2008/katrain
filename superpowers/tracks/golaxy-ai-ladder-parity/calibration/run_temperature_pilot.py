#!/usr/bin/env python3
"""Strict serial runner for the preregistered HumanSL temperature pilot."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parents[4]
os.environ.setdefault("KIVY_NO_ARGS", "1")
sys.path.insert(0, str(REPO_ROOT))

import httpx

import adapters
import run_selfplay
import temperature_pilot as pilot


LAUNCH_SNAPSHOT_NAME = "launch_snapshot.json"
SUMMARY_NAME = "summary.json"
REPORT_NAME = "report.md"


def checkpoint_path(results_dir: Path | str, matchup: Mapping[str, object]) -> Path:
    player_a = run_selfplay._fname(matchup["a"]["canonical_label"])
    player_b = run_selfplay._fname(matchup["b"]["canonical_label"])
    return Path(results_dir) / f"selfplay_{matchup['phase']}_{player_a}__vs__{player_b}.jsonl"


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _snapshot_payload(capabilities: Mapping[str, object], manifest_sha256: str) -> dict:
    if not isinstance(manifest_sha256, str) or len(manifest_sha256) != 64:
        raise ValueError("manifest digest is invalid")
    health = run_selfplay._json_value(capabilities)
    model = health.get("models", {}).get("b28", {})
    if (
        health.get("capability_schema") != 1
        or health.get("default_model") != "b28"
        or model.get("running") is not True
        or model.get("model_sha256_verified") is not True
        or model.get("human_model_sha256_verified") is not True
        or not model.get("model_sha256")
        or not model.get("human_model_sha256")
    ):
        raise ValueError("temperature pilot requires verified native default b28 with humanv0 attached")
    first = pilot.MATCHUPS[0]
    players = {
        "A": run_selfplay.make_player(first.a.canonical_label),
        "B": run_selfplay.make_player(first.b.canonical_label),
    }
    identities = run_selfplay._preflight_capabilities(capabilities, players)
    if identities["A"] != identities["B"] or identities["A"].get("selected_model") != "b28":
        raise ValueError("temperature pilot player identity is not native default b28 + humanv0")
    payload = {
        "schema_version": 1,
        "protocol": pilot.PROTOCOL_VERSION,
        "manifest_sha256": manifest_sha256,
        "capability_snapshot": health,
        "identities": identities,
    }
    payload["snapshot_sha256"] = pilot.canonical_digest(payload, exclude="snapshot_sha256")
    return payload


def _load_launch_snapshot(path: Path, manifest_sha256: str) -> dict:
    try:
        snapshot = run_selfplay._strict_json_loads(path.read_bytes(), context="temperature pilot launch snapshot")
    except OSError as exc:
        raise ValueError(f"cannot read temperature pilot launch snapshot: {exc}") from exc
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("schema_version") != 1
        or snapshot.get("protocol") != pilot.PROTOCOL_VERSION
        or snapshot.get("manifest_sha256") != manifest_sha256
        or snapshot.get("snapshot_sha256") != pilot.canonical_digest(snapshot, exclude="snapshot_sha256")
    ):
        raise ValueError("temperature pilot launch snapshot is invalid")
    capabilities = adapters.retain_health_snapshot(snapshot.get("capability_snapshot"))
    expected = _snapshot_payload(capabilities, manifest_sha256)
    if snapshot != expected:
        raise ValueError("temperature pilot launch snapshot identity is invalid")
    return snapshot


def ensure_launch_snapshot(results_dir: Path | str, capabilities: Mapping[str, object], manifest_sha256: str) -> dict:
    results = Path(results_dir)
    results.mkdir(parents=True, exist_ok=True)
    path = results / LAUNCH_SNAPSHOT_NAME
    expected = _snapshot_payload(capabilities, manifest_sha256)
    try:
        with path.open("xb") as output:
            output.write(_json_bytes(expected))
            output.flush()
    except FileExistsError:
        frozen = _load_launch_snapshot(path, manifest_sha256)
        if frozen != expected:
            raise ValueError("live health identity does not match frozen launch snapshot")
        return frozen
    return expected


def dry_run(manifest_path: Path | str, results_dir: Path | str, *, repo_root: Path | str = REPO_ROOT) -> None:
    manifest = pilot.validate_manifest_file(manifest_path, repo_root)
    print(f"manifest_sha256 {manifest['manifest_sha256']}")
    for index, matchup in enumerate(manifest["matchups"], 1):
        print(f"matchup {index}/9 {matchup['matchup_id']}")
        print(f"checkpoint {checkpoint_path(results_dir, matchup)}")
        for allocation in manifest["opening_suite"]["allocations"]:
            moves = ",".join(str(move) for move in allocation["moves"])
            print(f"attempt {allocation['attempt']} opening {allocation['id']} moves {moves}")


def _wide_root_noise() -> float:
    engine = dict(run_selfplay._MockKaTrainForConfig(force_package_config=True).config("engine"))
    return adapters.load_engine_wide_root_noise(engine)


async def run_pilot(
    manifest_path: Path | str,
    base_url: str,
    results_dir: Path | str,
    *,
    repo_root: Path | str = REPO_ROOT,
) -> dict:
    manifest = pilot.validate_manifest_file(manifest_path, repo_root)
    evidence = []
    openings = [
        {"id": allocation["id"], "moves": list(allocation["moves"])}
        for allocation in manifest["opening_suite"]["allocations"]
    ]
    async with httpx.AsyncClient() as client:
        capabilities = await adapters.fetch_health_snapshot(client, base_url)
        launch = ensure_launch_snapshot(results_dir, capabilities, manifest["manifest_sha256"])
        for matchup in manifest["matchups"]:
            context = {
                "protocol_version": pilot.PROTOCOL_VERSION,
                "manifest_path": str(Path(manifest_path)),
                "manifest_sha256": manifest["manifest_sha256"],
                "canonical_matchup_id": matchup["matchup_id"],
                "launch_snapshot_sha256": launch["snapshot_sha256"],
            }
            result = await run_selfplay.run_matchup(
                matchup["a"]["canonical_label"],
                matchup["b"]["canonical_label"],
                matchup["target_complete_pairs"],
                client=client,
                base_url=base_url,
                wrn=_wide_root_noise(),
                out_dir=Path(results_dir),
                capabilities=capabilities,
                phase=matchup["phase"],
                max_pair_attempts=matchup["max_pair_attempts"],
                exact_openings=openings,
                pilot_context=context,
            )
            evidence.append(
                {
                    "matchup_id": matchup["matchup_id"],
                    "a_wins": result.get("a_wins"),
                    "complete_pairs": result.get("complete_pairs"),
                    "identity_valid": True,
                }
            )
            if result.get("complete_pairs") != matchup["target_complete_pairs"]:
                break
    return pilot.classify_pilot(evidence)


def _validated_checkpoint_evidence(
    path: Path,
    matchup: Mapping[str, object],
    manifest: Mapping[str, object],
    launch: Mapping[str, object],
    manifest_path: Path | str,
) -> dict:
    if not path.is_file():
        return {
            "matchup_id": matchup["matchup_id"],
            "a_wins": 0,
            "complete_pairs": 0,
            "identity_valid": False,
        }
    capabilities = adapters.retain_health_snapshot(launch["capability_snapshot"])
    players = {
        "A": run_selfplay.make_player(matchup["a"]["canonical_label"]),
        "B": run_selfplay.make_player(matchup["b"]["canonical_label"]),
    }
    identities = run_selfplay._preflight_capabilities(capabilities, players)
    if identities != launch["identities"]:
        raise ValueError("checkpoint identities do not match the frozen launch snapshot")
    openings = [
        {"id": allocation["id"], "moves": list(allocation["moves"])}
        for allocation in manifest["opening_suite"]["allocations"]
    ]
    context = {
        "protocol_version": pilot.PROTOCOL_VERSION,
        "manifest_path": str(Path(manifest_path)),
        "manifest_sha256": manifest["manifest_sha256"],
        "canonical_matchup_id": matchup["matchup_id"],
        "launch_snapshot_sha256": launch["snapshot_sha256"],
    }
    configuration = run_selfplay._matchup_configuration(
        players,
        identities,
        capabilities=capabilities,
        wide_root_noise=_wide_root_noise(),
        target_pairs=matchup["target_complete_pairs"],
        max_pair_attempts=matchup["max_pair_attempts"],
        phase=matchup["phase"],
        opening_suite=run_selfplay.load_opening_suite(),
        exact_openings=openings,
        pilot_context=context,
    )
    fingerprint = run_selfplay._configuration_fingerprint(configuration)
    run_selfplay._already_done(path, fingerprint, configuration)
    records = run_selfplay._parse_strict_jsonl(path.read_bytes(), context="temperature pilot checkpoint")
    _validate_exact_checkpoint_schedule(records[1:], matchup, manifest)
    sample = run_selfplay.complete_pair_sample(records[1:], phase=matchup["phase"])
    return {
        "matchup_id": matchup["matchup_id"],
        "a_wins": sample["a_wins"],
        "complete_pairs": sample["complete_pairs"],
        "identity_valid": True,
        "decision_games": sample["games"],
        "inconclusive_pairs": sample["inconclusive_pairs"],
        "checkpoint": str(path),
        "checkpoint_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _validate_exact_checkpoint_schedule(
    records: list[Mapping[str, object]], matchup: Mapping[str, object], manifest: Mapping[str, object]
) -> None:
    openings = [
        {"id": allocation["id"], "moves": list(allocation["moves"])}
        for allocation in manifest["opening_suite"]["allocations"]
    ]
    run_selfplay.schedule_pair_games(
        records,
        openings,
        phase=matchup["phase"],
        max_pair_attempts=matchup["max_pair_attempts"],
        cycle_openings=False,
    )


def _collect_evidence(
    manifest_path: Path | str,
    results_dir: Path | str,
    *,
    repo_root: Path | str,
) -> tuple[dict, list[dict]]:
    manifest = pilot.validate_manifest_file(manifest_path, repo_root)
    results = Path(results_dir)
    launch_path = results / LAUNCH_SNAPSHOT_NAME
    if not launch_path.is_file():
        return manifest, [
            {
                "matchup_id": matchup["matchup_id"],
                "a_wins": 0,
                "complete_pairs": 0,
                "identity_valid": False,
            }
            for matchup in manifest["matchups"]
        ]
    launch = _load_launch_snapshot(launch_path, manifest["manifest_sha256"])
    evidence = [
        _validated_checkpoint_evidence(checkpoint_path(results, matchup), matchup, manifest, launch, manifest_path)
        for matchup in manifest["matchups"]
    ]
    return manifest, evidence


def check_pilot(
    manifest_path: Path | str,
    results_dir: Path | str | None = None,
    *,
    repo_root: Path | str = REPO_ROOT,
) -> dict:
    manifest = pilot.validate_manifest_file(manifest_path, repo_root)
    if results_dir is None:
        return {
            "status": "valid",
            "manifest_sha256": manifest["manifest_sha256"],
            "matchups": len(manifest["matchups"]),
            "planned_games": sum(2 * row["target_complete_pairs"] for row in manifest["matchups"]),
        }
    _manifest, evidence = _collect_evidence(manifest_path, results_dir, repo_root=repo_root)
    return pilot.classify_pilot(evidence)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def summarize_pilot(
    manifest_path: Path | str,
    results_dir: Path | str,
    *,
    repo_root: Path | str = REPO_ROOT,
) -> dict:
    manifest, evidence = _collect_evidence(manifest_path, results_dir, repo_root=repo_root)
    results = Path(results_dir)
    launch_path = results / LAUNCH_SNAPSHOT_NAME
    launch = _load_launch_snapshot(launch_path, manifest["manifest_sha256"]) if launch_path.is_file() else None
    gate = pilot.classify_pilot(evidence)
    classifications = {row["matchup_id"]: row for row in gate.get("matchups", [])}
    enriched_evidence = []
    for matchup, row in zip(manifest["matchups"], evidence):
        complete_pairs = row.get("complete_pairs", 0)
        decision_games = row.get("decision_games", 2 * complete_pairs)
        a_wins = row.get("a_wins", 0)
        enriched_evidence.append(
            {
                **row,
                "player_a": matchup["a"],
                "player_b": matchup["b"],
                "expected_stronger": matchup["expected_stronger"],
                "target_games": 2 * matchup["target_complete_pairs"],
                "eligible_games": decision_games,
                "a_losses": decision_games - a_wins if type(a_wins) is int else None,
                "classification": classifications.get(matchup["matchup_id"], {}).get("classification", "incomplete"),
                "checkpoint": row.get("checkpoint", str(checkpoint_path(results, matchup))),
                "checkpoint_sha256": row.get("checkpoint_sha256"),
            }
        )
    summary = {
        "protocol": pilot.PROTOCOL_VERSION,
        "manifest_sha256": manifest["manifest_sha256"],
        "launch_snapshot_sha256": launch.get("snapshot_sha256") if launch else None,
        "model_identities": launch.get("identities") if launch else None,
        "runtime_sources": manifest["runtime_sources"],
        **gate,
        "evidence": enriched_evidence,
    }
    report_lines = [
        "# HumanSL temperature pilot",
        "",
        f"overall: {summary['status']}",
        f"manifest_sha256: {manifest['manifest_sha256']}",
        f"launch_snapshot_sha256: {summary['launch_snapshot_sha256']}",
        f"model_identities: {json.dumps(summary['model_identities'], sort_keys=True, ensure_ascii=False)}",
        "runtime_sources:",
        *[f"- {source}: {digest}" for source, digest in summary["runtime_sources"].items()],
        "",
    ]
    for row in enriched_evidence:
        report_lines.append(
            f"- {row['matchup_id']}: A {row.get('a_wins', 0)}-{row.get('a_losses')}/{row['target_games']}, "
            f"eligible={row.get('eligible_games', 0)}, complete_pairs={row.get('complete_pairs', 0)}, "
            f"inconclusive_pairs={row.get('inconclusive_pairs', 0)}, class={row['classification']}, "
            f"A={row['player_a']['canonical_label']}, B={row['player_b']['canonical_label']}, "
            f"identity_valid={row.get('identity_valid') is True}, checkpoint={row['checkpoint']}, "
            f"checkpoint_sha256={row['checkpoint_sha256']}"
        )
    _atomic_write(results / SUMMARY_NAME, _json_bytes(summary))
    _atomic_write(results / REPORT_NAME, ("\n".join(report_lines) + "\n").encode("utf-8"))
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-manifest")
    create.add_argument("--implementation-base", required=True)
    create.add_argument("--out", required=True, type=Path)

    check = commands.add_parser("check")
    check.add_argument("--manifest", required=True, type=Path)
    check.add_argument("--results-dir", type=Path)

    dry = commands.add_parser("dry-run")
    dry.add_argument("--manifest", required=True, type=Path)
    dry.add_argument("--results-dir", required=True, type=Path)

    run = commands.add_parser("run")
    run.add_argument("--manifest", required=True, type=Path)
    run.add_argument("--base-url", required=True)
    run.add_argument("--results-dir", required=True, type=Path)

    summarize = commands.add_parser("summarize")
    summarize.add_argument("--manifest", required=True, type=Path)
    summarize.add_argument("--results-dir", required=True, type=Path)
    return parser


def _print_result(result: Mapping[str, object]) -> None:
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False))


def main() -> int:
    args = build_arg_parser().parse_args()
    if args.command == "create-manifest":
        created = pilot.create_manifest(args.out, REPO_ROOT, args.implementation_base)
        _print_result(
            {
                "status": "created",
                "path": str(args.out),
                "manifest_sha256": created["manifest_sha256"],
            }
        )
        return 0
    if args.command == "check":
        result = check_pilot(args.manifest, args.results_dir)
    elif args.command == "dry-run":
        dry_run(args.manifest, args.results_dir)
        return 0
    elif args.command == "run":
        result = asyncio.run(run_pilot(args.manifest, args.base_url, args.results_dir))
    elif args.command == "summarize":
        result = summarize_pilot(args.manifest, args.results_dir)
    else:  # pragma: no cover - argparse restricts the command
        raise AssertionError(args.command)
    _print_result(result)
    return 2 if result.get("status") == "incomplete" else 0


if __name__ == "__main__":
    raise SystemExit(main())
