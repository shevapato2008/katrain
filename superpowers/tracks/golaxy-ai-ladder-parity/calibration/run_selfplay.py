#!/usr/bin/env python3
"""Self-play strength assessment (operator-run): pit two of OUR OWN KataGo configs against
each other via the local /analyze engine, adjudicated by an impartial b28 referee. NO Golaxy,
NO token, NO daily budget -- pure self-assessment of how humanSL ranks scale with search.

Reuses the TESTED calibration primitives:
  * adapters query/identity -- builds the canonical ladder query and verifies the executed model
  * ladder_calibration.play_one_game -- the fail-closed alternating game loop
  * adapters.adjudicate     -- one b28@200 black-relative settled score; unlike calibration,
                               self-play does not run a second stability recheck

A "player" is a minimal LadderRung built from a spec "<profile>@<visits>":
  * rank_9d@1     -> mechanism 'humansl'        (humanv0 human policy @1 visit, weighted sample;
                     this is the vanilla HumanSL ladder config)
  * rank_9d@1s    -> mechanism 'humansl'        (humanv0 human policy @1 visit, argmax)
  * rank_9d@40    -> mechanism 'humansl_search' (b18 main model + humanv0 using the canonical
                     nonzero PIKL recipe, then select the top search move)
  * b28@20        -> mechanism 'net_search'     (pure b28 @20, no human profile)
HumanSL search defaults to a 40-visit minimum. Lower visits require the explicit operator-only
experimental floor option. The HTTP adapter routes b18/b28 explicitly and rejects missing or
mismatched wrapper attestation. Games end on the first pass or the 400-move cap, then b28 scores.

Usage:
    KIVY_NO_ARGS=1 uv run python \
      superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py \
      --matchups "rank_9d@80:rank_9d@40:20,rank_9d@40:b28@20:40" \
      --phase confirm \
      --base-url http://127.0.0.1:8000 \
      --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl

Each matchup is "A:B:fully-conclusive-pairs". Every frozen opening is played with A as Black and
White; a pair with either game inconclusive contributes zero decision games. Checkpoints are
phase-isolated and resumable, including completion of an interrupted color pair."""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import gzip
import hashlib
import io
import json
import logging
import math
import os
import re
import stat as stat_module
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from typing import List, Mapping, Optional, Tuple

import httpx

try:  # POSIX (macOS/Linux)
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - exercised by backend-selection tests
    _fcntl = None

try:  # Windows
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - exercised by backend-selection tests
    _msvcrt = None

os.environ.setdefault("KIVY_NO_ARGS", "1")  # keep Kivy from hijacking our argv (see run_calibration)

sys.path.insert(0, str(Path(__file__).parent))
import adapters  # noqa: E402
import temperature_pilot  # noqa: E402

from katrain.core.base_katrain import KaTrainBase  # noqa: E402
from katrain.core.ladder import (  # noqa: E402
    HUMANSL_PIKL_BASELINE,
    LadderMoveError,
    LadderRung,
    _valid_policy,
    colrow_to_golaxy,
    golaxy_to_colrow,
    pick_ladder_move,
    pick_ladder_rung_move,
    pick_temperature_policy,
    rung_strength_spec,
    validate_analysis_attestation,
)
from katrain.core.ladder_calibration import play_one_game, elo_from_winrate, GameOutcome  # noqa: E402
from katrain.core.game import BaseGame, IllegalMoveException  # noqa: E402
from katrain.core.sgf_parser import Move  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_selfplay")

_RESULTS_DIR = Path(__file__).parent / "results"
DEFAULT_OUT_DIR = _RESULTS_DIR / "selfplay_v2_pikl"
LEGACY_OUT_DIR = _RESULTS_DIR / "selfplay"
_RANK_TOKEN = r"(?:[1-9]d|(?:[1-9]|1[0-9]|20)k)"
_RANK_PROFILE_RE = re.compile(rf"(?:rank|preaz)_{_RANK_TOKEN}(?:_{_RANK_TOKEN})?\Z")
_PROYEAR_PROFILE_RE = re.compile(r"proyear_([0-9]{4})\Z")
CHECKPOINT_SCHEMA = 3
PILOT_CHECKPOINT_MAX_BYTES = 32 * 1024 * 1024
PILOT_CHECKPOINT_MAX_LINE_BYTES = 4 * 1024 * 1024
SELECTION_ALGORITHM_VERSION = "selfplay-selection-v1"
GENERIC_TEMPERATURE_PROTOCOL_VERSION = "humansl-temperature-generic-v1"
SYMMETRY_SETTINGS = {"mode": "katago-default", "requested_symmetry": None}
OPENING_SUITE_PATH = Path(__file__).parent / "opening_suite_v1.json"
BOUNDARY_OPENING_SUITE_PATH = Path(__file__).parent / "opening_suite_boundary_v1.json"
BOUNDARY_OPENING_ALLOCATION_PATH = Path(__file__).parent / "opening_allocation_boundary_v1.json"
KNOWN_ENDPOINTS_PATH = Path(__file__).parent / "known_endpoints_exp3_v1.json"
KNOWN_ENDPOINT_SOURCE_ROOT = (Path(__file__).resolve().parent / "results").resolve()
MAX_KNOWN_ENDPOINT_COMPRESSED_BYTES = 1024 * 1024
MAX_KNOWN_ENDPOINT_DECOMPRESSED_BYTES = 16 * 1024 * 1024
MAX_KNOWN_ENDPOINT_SUMMARY_BYTES = 1024 * 1024
OPENING_SUITE_ID = "humansl-opening-suite-v1"
OPENING_SUITE_SEED = 20260721
BOARD_SIZE = 19
KOMI = 7.5
RULES = "chinese"
MOVE_CAP = 400
REFEREE_VISITS = 200
ADJUDICATION_ALGORITHM_VERSION = "b28-settled-score-v1"
_IDENTITY_FIELDS = (
    "selected_model",
    "model_path",
    "model_sha256",
    "human_model_path",
    "human_model_sha256",
    "katago_version",
)
WILSON_Z95 = 1.959963984540054
BOUNDARY_PROTOCOL_VERSION = "exp3-boundary-v1"
BOUNDARY_TRANSITIONS = (
    "rank_5d__rank_6d",
    "rank_6d__rank_7d",
    "rank_7d__rank_8d",
    "rank_8d__rank_9d",
)
BOUNDARY_GRID = (2, 5, 10, 20, 30, 40)
BOUNDARY_SCREEN_VISITS = (2, 5, 10, 20, 30)
BOUNDARY_CONFIRM_VISITS = BOUNDARY_GRID
BOUNDARY_POINT_ESTIMATE_PASS_RULE = "A decision-game point estimate >= 50% at exactly 10 complete color pairs"
BOUNDARY_SEARCH_ORDER = {"start": 20, "after_pass": [10, 5, 2], "after_fail": [30], "known_pass": 40}
BOUNDARY_STOPPING_RULE = (
    "stop at first failure after descending from 20, after testing 30 following a failure at 20, "
    "or after a pass at the floor 2; abort at the attempt cap"
)


def wilson_interval(wins: int, n: int) -> Tuple[float, float]:
    """Return the two-sided 95% Wilson score interval for a binomial sample."""
    if type(wins) is not int or type(n) is not int or n <= 0 or not 0 <= wins <= n:
        raise ValueError("Wilson inputs require integer 0 <= wins <= n and n > 0")
    p = wins / n
    z2 = WILSON_Z95 * WILSON_Z95
    denominator = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denominator
    radius = WILSON_Z95 * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def required_conclusive_pairs(phase: str, *, experiment4: bool = False) -> int:
    if phase not in {"screen", "confirm"}:
        raise ValueError("phase must be 'screen' or 'confirm'")
    if experiment4 and phase != "confirm":
        raise ValueError("experiment-4 requires confirm phase")
    return 40 if experiment4 else (10 if phase == "screen" else 20)


def classify_seam(wins: int, n: int, *, experiment4: bool = False) -> str:
    minimum_games = 2 * required_conclusive_pairs("confirm", experiment4=experiment4)
    if n < minimum_games or n % 2:
        return "insufficient_pairs"
    low, high = wilson_interval(wins, n)
    if low > 0.5:
        return "a_stronger"
    if high < 0.5:
        return "a_weaker"
    return "inconclusive"


def opening_suite_checksum(payload: Mapping[str, object]) -> str:
    canonical = {key: value for key, value in payload.items() if key != "checksum"}
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_manifest_digest(payload: Mapping[str, object], digest_field: Optional[str] = None) -> str:
    canonical = {key: value for key, value in payload.items() if key != digest_field}
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _strict_json_loads(data: object, *, context: str) -> object:
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{context} strict JSON is not UTF-8: {exc}") from exc
    if not isinstance(data, str):
        raise ValueError(f"{context} strict JSON input must be text or bytes")
    try:
        return json.loads(
            data,
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"invalid JSON constant {value}")),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{context} strict JSON is invalid: {exc}") from exc


def _parse_strict_jsonl(data: object, *, context: str) -> List[dict]:
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{context} strict JSONL is not UTF-8: {exc}") from exc
    if not isinstance(data, str):
        raise ValueError(f"{context} strict JSONL input must be text or bytes")
    records = []
    for line_number, line in enumerate(data.splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = _strict_json_loads(line, context=f"{context} line {line_number}")
        except ValueError as exc:
            raise ValueError(f"{context} strict JSONL is invalid: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{context} strict JSONL line {line_number} must be an object")
        records.append(record)
    return records


def _load_strict_json(path: Path) -> dict:
    try:
        payload = _strict_json_loads(Path(path).read_bytes(), context=f"strict JSON file {path}")
    except OSError as exc:
        raise ValueError(f"cannot load strict JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"strict JSON root in {path} must be an object")
    return payload


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_path(value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("known endpoint source path is malformed")
    path = Path(value)
    if path.is_absolute():
        raise ValueError("known endpoint source path must be relative and contained under results")
    if ".." in path.parts:
        raise ValueError("known endpoint source path traversal is forbidden")
    resolved = (Path(__file__).resolve().parent / path).resolve()
    try:
        resolved.relative_to(KNOWN_ENDPOINT_SOURCE_ROOT)
    except ValueError as exc:
        raise ValueError("known endpoint source path must be relative and contained under results") from exc
    return resolved


def _read_bounded(path: Path, limit: int, *, label: str) -> bytes:
    try:
        if path.stat().st_size > limit:
            raise ValueError(f"known endpoint {label} exceeds size limit {limit}")
        with path.open("rb") as source:
            data = source.read(limit + 1)
    except OSError as exc:
        raise ValueError(f"cannot read known endpoint {label}: {exc}") from exc
    if len(data) > limit:
        raise ValueError(f"known endpoint {label} exceeds size limit {limit}")
    return data


def _decompress_bounded(data: bytes, limit: int) -> bytes:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as source:
            decompressed = source.read(limit + 1)
    except (EOFError, OSError, gzip.BadGzipFile) as exc:
        raise ValueError(f"cannot decompress known endpoint archive: {exc}") from exc
    if len(decompressed) > limit:
        raise ValueError(f"known endpoint decompressed archive exceeds size limit {limit}")
    return decompressed


def _git_output(arguments: List[str], *, cwd: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(cwd), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise ValueError(f"cannot inspect boundary source revision: git unavailable: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}"
        raise ValueError(f"cannot inspect boundary source revision: git failed: {detail}")
    return completed.stdout.strip()


def _git_returncode(arguments: List[str], *, cwd: Path) -> int:
    try:
        completed = subprocess.run(
            ["git", "-C", str(cwd), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise ValueError(f"cannot inspect boundary source revision: git unavailable: {exc}") from exc
    if completed.returncode not in {0, 1}:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}"
        raise ValueError(f"cannot inspect boundary source revision: git failed: {detail}")
    return completed.returncode


def load_boundary_source_snapshot(expected_source_revision: Optional[str]) -> dict:
    if not isinstance(expected_source_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", expected_source_revision):
        raise ValueError("boundary protocol requires --expected-source-revision as a full 40-hex lowercase commit")
    checkout_path = Path(__file__).resolve().parent
    root_text = _git_output(["rev-parse", "--show-toplevel"], cwd=checkout_path)
    try:
        git_root = Path(root_text).resolve(strict=True)
        Path(__file__).resolve().relative_to(git_root)
    except (OSError, ValueError) as exc:
        raise ValueError("boundary source git root does not contain the self-play harness") from exc
    if _git_returncode(["symbolic-ref", "--quiet", "HEAD"], cwd=git_root) != 1:
        raise ValueError("boundary source must be checked out at detached HEAD")
    source_revision = _git_output(["rev-parse", "HEAD"], cwd=git_root)
    if not re.fullmatch(r"[0-9a-f]{40}", source_revision):
        raise ValueError("git HEAD did not resolve to a full 40-hex commit")
    if source_revision != expected_source_revision:
        raise ValueError(
            f"boundary source revision {source_revision} does not match expected {expected_source_revision}"
        )
    tracked_status = _git_output(["status", "--porcelain=v1", "--untracked-files=no"], cwd=git_root)
    if tracked_status:
        raise ValueError("boundary source tracked files or index are not clean")
    return {
        "source_revision": source_revision,
        "expected_source_revision": expected_source_revision,
        "source_tree_clean": True,
        "detached": True,
        "source_git_root": str(git_root),
    }


def _validate_boundary_source_snapshot(snapshot: object, expected_source_revision: Optional[str]) -> dict:
    if not isinstance(expected_source_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", expected_source_revision):
        raise ValueError("boundary protocol requires --expected-source-revision as a full 40-hex lowercase commit")
    if not isinstance(snapshot, Mapping):
        raise ValueError("boundary source snapshot is malformed")
    source_git_root = snapshot.get("source_git_root")
    if not isinstance(source_git_root, str) or not Path(source_git_root).is_absolute():
        raise ValueError("boundary source snapshot git root must be absolute")
    try:
        resolved_root = str(Path(source_git_root).resolve(strict=True))
    except OSError as exc:
        raise ValueError(f"boundary source snapshot git root cannot be resolved: {exc}") from exc
    expected = {
        "source_revision": expected_source_revision,
        "expected_source_revision": expected_source_revision,
        "source_tree_clean": True,
        "detached": True,
        "source_git_root": resolved_root,
    }
    if snapshot != expected:
        raise ValueError("boundary source snapshot does not match the expected clean revision")
    return dict(expected)


def validate_boundary_out_dir(path: Path, source_snapshot: Mapping[str, object]) -> Path:
    supplied = Path(path)
    if not supplied.is_absolute():
        raise ValueError("boundary protocol --out must be supplied as an absolute path")
    resolved = supplied.resolve()
    source_root_value = source_snapshot.get("source_git_root")
    if not isinstance(source_root_value, str) or not Path(source_root_value).is_absolute():
        raise ValueError("boundary source snapshot git root must be absolute")
    try:
        source_root = Path(source_root_value).resolve(strict=True)
        resolved.relative_to(source_root)
    except OSError as exc:
        raise ValueError(f"boundary source git root cannot be resolved: {exc}") from exc
    except ValueError:
        return resolved
    raise ValueError("boundary protocol --out must resolve outside the source git root/worktree")


class _OpeningBoardConfig:
    @staticmethod
    def config(key):
        return 0 if key == "game/handicap" else "chinese"


def _validate_opening_legality(moves: List[int], board_size: int) -> None:
    game = BaseGame(
        _OpeningBoardConfig(),
        game_properties={"SZ": board_size, "KM": KOMI, "RU": RULES},
        bypass_config=True,
    )
    for ply, wire in enumerate(moves):
        colrow = golaxy_to_colrow(wire, board_size)
        if colrow == "pass":
            raise ValueError("opening moves must not contain pass")
        try:
            game.play(Move(colrow, player="B" if ply % 2 == 0 else "W"))
        except IllegalMoveException as exc:
            raise ValueError(f"opening is not legal at ply {ply}: {exc}") from exc


def load_opening_suite(path: Path = OPENING_SUITE_PATH) -> dict:
    try:
        payload = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load opening suite: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("suite_id") != OPENING_SUITE_ID:
        raise ValueError(f"opening suite ID must be {OPENING_SUITE_ID!r}")
    if type(payload.get("seed")) is not int or payload["seed"] != OPENING_SUITE_SEED:
        raise ValueError(f"opening suite seed must be documented as {OPENING_SUITE_SEED}")
    if payload.get("board_size") != BOARD_SIZE:
        raise ValueError(f"opening suite board size must be {BOARD_SIZE}")
    openings = payload.get("openings")
    if not isinstance(openings, list) or len(openings) < 20:
        raise ValueError("opening suite requires at least 20 openings")
    seen_ids, seen_prefixes = set(), set()
    for opening in openings:
        if not isinstance(opening, dict) or not isinstance(opening.get("id"), str) or not opening["id"]:
            raise ValueError("opening suite entry has invalid ID")
        if opening["id"] in seen_ids:
            raise ValueError("opening IDs must be unique")
        seen_ids.add(opening["id"])
        moves = opening.get("moves")
        if not isinstance(moves, list) or not moves:
            raise ValueError("opening moves must be a nonempty list")
        if any(type(move) is not int or not 0 <= move < BOARD_SIZE * BOARD_SIZE for move in moves):
            raise ValueError("opening move is outside coordinate bounds")
        prefix = tuple(moves)
        if prefix in seen_prefixes:
            raise ValueError("opening prefixes must be unique")
        seen_prefixes.add(prefix)
        _validate_opening_legality(moves, BOARD_SIZE)
    actual_checksum = payload.get("checksum")
    expected_checksum = opening_suite_checksum(payload)
    if not isinstance(actual_checksum, str) or actual_checksum != expected_checksum:
        raise ValueError(f"opening suite checksum mismatch: expected {expected_checksum}")
    return payload


def load_boundary_opening_allocation(
    suite_path: Path = BOUNDARY_OPENING_SUITE_PATH,
    allocation_path: Path = BOUNDARY_OPENING_ALLOCATION_PATH,
) -> Tuple[dict, dict]:
    suite = _load_strict_json(Path(suite_path))
    allocation = _load_strict_json(Path(allocation_path))
    if suite.get("suite_id") != "humansl-boundary-opening-suite-v1":
        raise ValueError("boundary opening suite ID mismatch")
    if suite.get("seed") != 20260722 or suite.get("board_size") != BOARD_SIZE:
        raise ValueError("boundary opening suite seed or board size mismatch")
    if suite.get("opening_count") != 1360:
        raise ValueError("boundary opening suite must declare exactly 1360 openings")
    if suite.get("checksum") != canonical_manifest_digest(suite, "checksum"):
        raise ValueError("boundary suite checksum mismatch")
    openings = suite.get("openings")
    if not isinstance(openings, list) or len(openings) != 1360:
        raise ValueError("boundary opening suite must contain exactly 1360 openings")
    by_id = {}
    sequences = set()
    for opening in openings:
        if not isinstance(opening, dict) or not isinstance(opening.get("id"), str):
            raise ValueError("boundary opening entry has invalid ID")
        moves = opening.get("moves")
        if (
            not isinstance(moves, list)
            or len(moves) != 8
            or any(type(move) is not int or not 0 <= move < BOARD_SIZE * BOARD_SIZE for move in moves)
            or len(set(moves)) != 8
        ):
            raise ValueError("boundary opening must contain eight distinct legal coordinates")
        sequence = tuple(moves)
        if opening["id"] in by_id or sequence in sequences:
            raise ValueError("boundary opening IDs and canonical sequences must be globally unique")
        _validate_opening_legality(moves, BOARD_SIZE)
        by_id[opening["id"]] = opening
        sequences.add(sequence)

    prior_sequences = {tuple(opening["moves"]) for opening in load_opening_suite()["openings"]}
    if sequences & prior_sequences:
        raise ValueError("boundary opening sequences must be disjoint from opening_suite_v1")
    if allocation.get("allocation_id") != "humansl-boundary-opening-allocation-v1":
        raise ValueError("boundary opening allocation ID mismatch")
    if allocation.get("protocol_version") != BOUNDARY_PROTOCOL_VERSION:
        raise ValueError("boundary opening allocation protocol mismatch")
    if allocation.get("suite_id") != suite["suite_id"] or allocation.get("suite_checksum") != suite["checksum"]:
        raise ValueError("boundary allocation suite checksum mismatch")
    if allocation.get("digest") != canonical_manifest_digest(allocation, "digest"):
        raise ValueError("boundary allocation digest mismatch")
    if allocation.get("transitions") != list(BOUNDARY_TRANSITIONS):
        raise ValueError("boundary allocation transitions mismatch")
    if allocation.get("screening_visits") != list(BOUNDARY_SCREEN_VISITS):
        raise ValueError("boundary screening grid mismatch")
    if allocation.get("confirmation_visits") != list(BOUNDARY_CONFIRM_VISITS):
        raise ValueError("boundary confirmation grid mismatch")
    if allocation.get("screening_attempt_cap") != 20 or allocation.get("confirmation_attempt_cap") != 40:
        raise ValueError("boundary allocation attempt caps mismatch")
    expected = {
        f"{phase}:{transition}:{visits}": cap
        for phase, visits_grid, cap in (
            ("screen", BOUNDARY_SCREEN_VISITS, 20),
            ("confirm", BOUNDARY_CONFIRM_VISITS, 40),
        )
        for transition in BOUNDARY_TRANSITIONS
        for visits in visits_grid
    }
    allocations = allocation.get("allocations")
    if not isinstance(allocations, dict) or set(allocations) != set(expected):
        raise ValueError("boundary allocation must have exactly 44 allocation keys")
    assigned = []
    for key, count in expected.items():
        ids = allocations[key]
        if not isinstance(ids, list) or len(ids) != count or any(item not in by_id for item in ids):
            raise ValueError(f"boundary allocation {key!r} is malformed")
        assigned.extend(ids)
    if len(assigned) != 1360 or len(set(assigned)) != 1360 or set(assigned) != set(by_id):
        raise ValueError("all 1360 boundary opening IDs must be assigned exactly once")
    return suite, allocation


def load_known_endpoints(path: Path = KNOWN_ENDPOINTS_PATH) -> Tuple[dict, str]:
    manifest = _load_strict_json(Path(path))
    if manifest.get("manifest_id") != "known-endpoints-exp3-v1":
        raise ValueError("known endpoints manifest ID mismatch")
    if manifest.get("protocol_version") != BOUNDARY_PROTOCOL_VERSION:
        raise ValueError("known endpoints protocol mismatch")
    digest = canonical_manifest_digest(manifest, "digest")
    if manifest.get("digest") != digest:
        raise ValueError("known endpoints manifest digest mismatch")
    endpoints = manifest.get("endpoints")
    if not isinstance(endpoints, list) or len(endpoints) != 4:
        raise ValueError("known endpoints manifest requires exactly four transitions")
    if [endpoint.get("transition") for endpoint in endpoints if isinstance(endpoint, dict)] != list(
        BOUNDARY_TRANSITIONS
    ):
        raise ValueError("known endpoints must cover the four transitions in canonical order")
    for endpoint in endpoints:
        if endpoint.get("visits") != 40 or endpoint.get("classification") != "pass":
            raise ValueError("known endpoint must be a passing visit-40 screen")
        archive_path = _source_path(endpoint.get("archive_path"))
        summary_path = _source_path(endpoint.get("source_summary_path"))
        archive = _read_bounded(archive_path, MAX_KNOWN_ENDPOINT_COMPRESSED_BYTES, label="compressed archive")
        decompressed = _decompress_bounded(archive, MAX_KNOWN_ENDPOINT_DECOMPRESSED_BYTES)
        summary_bytes = _read_bounded(summary_path, MAX_KNOWN_ENDPOINT_SUMMARY_BYTES, label="summary")
        if _sha256_bytes(archive) != endpoint.get("archive_sha256"):
            raise ValueError("known endpoint archive SHA-256 mismatch")
        if _sha256_bytes(decompressed) != endpoint.get("decompressed_sha256"):
            raise ValueError("known endpoint decompressed SHA-256 mismatch")
        if _sha256_bytes(summary_bytes) != endpoint.get("source_summary_sha256"):
            raise ValueError("known endpoint summary SHA-256 mismatch")
        try:
            checkpoint_records = _parse_strict_jsonl(decompressed, context="known endpoint checkpoint archive")
            header, games = checkpoint_records[0], checkpoint_records[1:]
            configuration = header["configuration"]
            summary = _strict_json_loads(summary_bytes, context="known endpoint source summary")
            low, high = endpoint["transition"].split("__")
            player_a = f"{low}@40"
            player_b = f"{high}@1s"
            matches = [
                matchup
                for matchup in summary["matchups"]
                if matchup.get("player_a") == player_a and matchup.get("player_b") == player_b
            ]
        except (IndexError, KeyError, TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"known endpoint source summary is malformed: {exc}") from exc
        if len(matches) != 1 or matches[0].get("a_winrate", -1) < 0.5:
            raise ValueError("known endpoint source summary does not contain its passing screen")
        if canonical_manifest_digest(matches[0]) != endpoint.get("source_summary_matchup_sha256"):
            raise ValueError("known endpoint source-summary matchup digest mismatch")
        if (
            header.get("record_type") != "header"
            or header.get("schema") != CHECKPOINT_SCHEMA
            or header.get("fingerprint") != _configuration_fingerprint(configuration)
        ):
            raise ValueError("known endpoint checkpoint header or fingerprint mismatch")
        players = configuration.get("players")
        if (
            not isinstance(players, Mapping)
            or players.get("A", {}).get("label") != player_a
            or players.get("B", {}).get("label") != player_b
            or players.get("A", {}).get("visits") != 40
            or players.get("B", {}).get("visits") != 1
        ):
            raise ValueError("known endpoint checkpoint transition does not match its manifest entry")
        if (
            configuration.get("phase") != "screen"
            or configuration.get("target_complete_pairs") != 10
            or configuration.get("max_pair_attempts") != 20
        ):
            raise ValueError("known endpoint checkpoint is not the fixed @40 screen protocol")
        for index, game in enumerate(games):
            if game.get("record_type") != "game" or game.get("fingerprint") != header["fingerprint"]:
                raise ValueError("known endpoint checkpoint game fingerprint mismatch")
            _validate_game_record(game, index, configuration)
        sample = complete_pair_sample(games, phase="screen")
        pair_attempts = 1 + max((game["pair_attempt"] for game in games), default=-1)
        reason_counts = {}
        for game in games:
            reason_counts[game["result"]] = reason_counts.get(game["result"], 0) + 1
        expected_summary = matches[0]
        if (
            sample["complete_pairs"] != 10
            or sample["games"] != expected_summary.get("decision_games")
            or sample["a_wins"] != expected_summary.get("a_wins")
            or sample["inconclusive_pairs"] != expected_summary.get("inconclusive_pairs")
            or pair_attempts != expected_summary.get("pair_attempts")
            or reason_counts != expected_summary.get("reason_counts")
            or expected_summary.get("target_complete_pairs") != 10
            or expected_summary.get("max_pair_attempts") != 20
            or expected_summary.get("phase") != "screen"
            or expected_summary.get("classification") != "screen_complete"
            or sample["a_wins"] / sample["games"] < 0.5
        ):
            raise ValueError("known endpoint checkpoint outcome does not match its passing source summary")
    return manifest, digest


def complete_pair_sample(records: List[Mapping[str, object]], *, phase: str) -> dict:
    grouped = {}
    for record in records:
        if record.get("phase") != phase:
            raise ValueError("checkpoint phase does not match this run")
        key = (record.get("pair_attempt"), record.get("opening_id"))
        color_index = record.get("color_index")
        if type(key[0]) is not int or type(color_index) is not int or color_index not in {0, 1}:
            raise ValueError("checkpoint pair key is malformed")
        pair = grouped.setdefault(key, {})
        if color_index in pair:
            raise ValueError("checkpoint contains duplicate pair color")
        pair[color_index] = record
    complete_pairs = games = wins = inconclusive_pairs = 0
    for pair in grouped.values():
        if len(pair) != 2:
            continue
        if all(record.get("conclusive") is True for record in pair.values()):
            complete_pairs += 1
            games += 2
            wins += sum(record.get("our_win") is True for record in pair.values())
        else:
            inconclusive_pairs += 1
    return {
        "complete_pairs": complete_pairs,
        "games": games,
        "a_wins": wins,
        "inconclusive_pairs": inconclusive_pairs,
    }


def schedule_pair_games(
    records: List[Mapping[str, object]],
    openings: List[Mapping[str, object]],
    *,
    phase: str,
    max_pair_attempts: int,
    cycle_openings: bool = True,
) -> List[dict]:
    if phase not in {"screen", "confirm"}:
        raise ValueError("phase must be screen or confirm")
    if type(max_pair_attempts) is not int or max_pair_attempts <= 0:
        raise ValueError("maximum pair attempts must be positive")
    if not openings:
        raise ValueError("opening suite is empty")
    if not cycle_openings and len(openings) != max_pair_attempts:
        raise ValueError("exact opening assignment must equal the maximum pair attempts")

    def opening_for(attempt):
        return openings[attempt % len(openings)] if cycle_openings else openings[attempt]

    completed_keys = set()
    for record in records:
        if record.get("phase") != phase:
            raise ValueError("checkpoint phase does not match this run")
        attempt = record.get("pair_attempt")
        color_index = record.get("color_index")
        if type(attempt) is not int or not 0 <= attempt < max_pair_attempts:
            raise ValueError("checkpoint exceeds maximum pair attempts")
        expected = opening_for(attempt)
        if record.get("opening_id") != expected["id"]:
            raise ValueError("checkpoint opening does not match pair schedule")
        if record.get("opening_moves") != expected["moves"]:
            raise ValueError("checkpoint opening history does not match pair schedule")
        key = (attempt, color_index)
        if type(color_index) is not int or color_index not in {0, 1} or key in completed_keys:
            raise ValueError("checkpoint contains duplicate or malformed pair color")
        completed_keys.add(key)
    scheduled = []
    for attempt in range(max_pair_attempts):
        opening = opening_for(attempt)
        for color_index, a_color in enumerate(("B", "W")):
            if (attempt, color_index) not in completed_keys:
                scheduled.append(
                    {
                        "phase": phase,
                        "opening_id": opening["id"],
                        "pair_attempt": attempt,
                        "color_index": color_index,
                        "a_color": a_color,
                        "initial_history": list(opening["moves"]),
                    }
                )
    return scheduled


class _MockKaTrainForConfig(KaTrainBase):
    """Config-only double: reads the SAME shipping engine block engine.py ships with."""


def _valid_humansl_profile(profile: str) -> bool:
    """Mirror KataGo SGFMetadata::getProfile's accepted named-profile ranges."""
    if _RANK_PROFILE_RE.fullmatch(profile):
        return True
    proyear = _PROYEAR_PROFILE_RE.fullmatch(profile)
    return proyear is not None and 1800 <= int(proyear.group(1)) <= 2023


def make_player(spec: str, *, experimental_min_humansl_search_visits: int = 40) -> Tuple[str, LadderRung, str]:
    """'rank_9d@40' / 'rank_9d@1s' / 'b18@12' / 'b28@20' -> player recipe.

    selection drives HOW the move is picked from the engine reply:
      * 'search'       -- top (min-order) moveInfo. net_search uses pure b28; humansl_search uses
                          explicitly routed b18 + humanv0 with the canonical nonzero PIKL recipe.
      * 'weighted'     -- weighted RANDOM sample of humanPolicy. vanilla humansl @1 (Band A config).
      * 'argmax_human' -- ARGMAX of humanPolicy at 1 visit (deterministic "top human move"). This is
                          the faithful 'humansl_search@1': a 1-visit SEARCH returns EMPTY moveInfos
                          (only the root is evaluated), so search-move-picking is impossible at V=1;
                          argmax over the (present) humanPolicy is the real "argmax@1" the spec means.
      * 'policy_argmax' -- ARGMAX of the pure network policy for b18@1.

    A trailing 's' is valid only for argmax_human at 1 visit ('rank_9d@1s'); plain 'rank_9d@1' is
    weighted vanilla HumanSL. HumanSL search requires at least the explicitly supplied experimental
    floor, which defaults to 40 visits. The floor must be a plain integer of at least 2."""
    if type(experimental_min_humansl_search_visits) is not int or experimental_min_humansl_search_visits < 2:
        raise ValueError("experimental HumanSL search minimum must be a plain int of at least 2")
    prof, sep, vs = spec.partition("@")
    temperature = None
    if sep and vs.startswith("1t"):
        if not _valid_humansl_profile(prof):
            raise ValueError("temperature players require a HumanSL profile")
        identity = temperature_pilot.temperature_player_identity(prof, vs[2:])
        temperature = float(identity.temperature)
        vs = "1"
    force_search = vs.endswith("s")  # trailing 's' -> argmax_human @1 (see docstring)
    if force_search:
        vs = vs[:-1]
    if not sep or not vs.isdigit() or int(vs) < 1:
        raise ValueError(
            f"bad player spec {spec!r} (want '<profile>@<visits>[s]', visits>=1; a trailing 's' means "
            "argmax@1, e.g. 'rank_9d@1s' = argmax humanPolicy @1 vs 'rank_9d@1' = weighted@1)"
        )
    visits = int(vs)
    if prof in {"b18", "b28"}:
        if force_search:
            raise ValueError("the 's' suffix is only supported by HumanSL '<profile>@1s'")
        mech, net, profile, label = "net_search", prof, None, f"{prof}@{visits}"
        selection = "policy_argmax" if prof == "b18" and visits == 1 else "search"
    elif _valid_humansl_profile(prof):
        if temperature is not None:
            mech, selection, label = "humansl", "temperature_weighted", identity.canonical_label
        elif visits == 1 and force_search:
            mech, selection, label = "humansl", "argmax_human", f"{prof}@1s"  # argmax humanPolicy @1
        elif visits == 1:
            mech, selection, label = "humansl", "weighted", f"{prof}@1"  # vanilla weighted humanSL
        elif force_search:
            raise ValueError("the 's' suffix is only supported by HumanSL '<profile>@1s'")
        elif visits < experimental_min_humansl_search_visits:
            raise ValueError(
                "HumanSL search has a supported minimum of "
                f"{experimental_min_humansl_search_visits} visits, got {visits}"
            )
        else:
            mech, selection, label = "humansl_search", "search", f"{prof}@{visits}"
        net = "humanv0" if visits == 1 else "b18"
        profile = prof
    else:
        raise ValueError(f"bad player profile {prof!r} (want 'b18', 'b28', or a humanSL profile like 'rank_9d')")
    rung = LadderRung(
        rung=0,
        golaxy_level_name=None,
        golaxy_api_level=None,
        display_elo=None,
        ref_rank=prof,
        rank_name=prof,
        net=net,
        mechanism=mech,
        selection={
            "weighted": "human_weighted",
            "temperature_weighted": "human_temperature",
            "argmax_human": "human_argmax",
            "policy_argmax": "native_policy_argmax",
            "search": "search",
        }[selection],
        human_sl_profile=profile,
        max_visits=visits,
        human_sl_params=dict(HUMANSL_PIKL_BASELINE) if mech == "humansl_search" else {},
        backend_hint="server",
        root_policy_temperature=1.0,
        human_policy_temperature=temperature,
    )
    return label, rung, selection


def _pick_argmax_human(hp: list, board_size: Tuple[int, int]) -> object:
    """ARGMAX of a humanPolicy vector -> (col,row0) bottom-origin, or 'pass'. Same index layout as
    ladder._weighted_policy_pick (idx = (by-y-1)*bx + x; last entry = pass)."""
    bx, by = board_size
    best_val, best = -1.0, None
    for x in range(bx):
        for y in range(by):
            idx = (by - y - 1) * bx + x
            if idx < len(hp) and hp[idx] > best_val:
                best_val, best = hp[idx], (x, y)
    if len(hp) > bx * by and hp[bx * by] > best_val:
        best = "pass"
    return best if best is not None else "pass"


def _generic_temperature_player_identity(canonical_matchup_id: str, player: str):
    if not isinstance(canonical_matchup_id, str) or canonical_matchup_id.count("__vs__") != 1:
        raise ValueError("generic canonical matchup ID is invalid")
    if player not in {"A", "B"}:
        raise ValueError("player must be A or B")
    label = canonical_matchup_id.split("__vs__")[0 if player == "A" else 1]
    profile, separator, temperature = label.partition("@1t")
    if not separator:
        raise ValueError("generic temperature side is not a temperature player")
    identity = temperature_pilot.temperature_player_identity(profile, temperature)
    if identity.canonical_label != label:
        raise ValueError("generic temperature label is not canonical")
    return identity


def _derive_generic_temperature_draw(
    *, manifest_sha256, canonical_matchup_id, pair_attempt, color_index, ply, player, include_audit=False
):
    """Freeze the pilot SHA256-u64 serialization for a non-preregistered generic matchup."""
    if not isinstance(manifest_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256):
        raise ValueError("manifest_sha256 must be a lowercase SHA-256 digest")
    if not isinstance(canonical_matchup_id, str) or canonical_matchup_id.count("__vs__") != 1:
        raise ValueError("generic canonical matchup ID is invalid")
    if type(pair_attempt) is not int or pair_attempt < 0 or type(ply) is not int or ply < 0:
        raise ValueError("generic temperature pair attempt and ply must be non-negative plain integers")
    if type(color_index) is not int or color_index not in {0, 1} or player not in {"A", "B"}:
        raise ValueError("generic temperature color or player is invalid")
    payload = [
        GENERIC_TEMPERATURE_PROTOCOL_VERSION,
        manifest_sha256,
        canonical_matchup_id,
        pair_attempt,
        color_index,
        ply,
        player,
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).digest()
    draw = int.from_bytes(digest[:8], "big", signed=False)
    return (encoded, digest.hex(), draw) if include_audit else draw


def _build_generic_sampling_trace(*, temperature, draw_u64, selected_index, policy, **context):
    identity = _generic_temperature_player_identity(context["canonical_matchup_id"], context["player"])
    if temperature != identity.temperature:
        raise ValueError("sampling trace must match the generic temperature player")
    if not _valid_policy(policy, BOARD_SIZE * BOARD_SIZE + 1):
        raise ValueError("sampling trace policy must contain exactly 362 valid entries")
    if type(selected_index) is not int or not 0 <= selected_index < len(policy) or policy[selected_index] <= 0:
        raise ValueError("sampling trace selected index is invalid")
    if draw_u64 != _derive_generic_temperature_draw(**context):
        raise ValueError("draw_u64 does not match the stateless generic draw")
    return {
        "ply": context["ply"],
        "player": context["player"],
        "temperature": temperature,
        "draw_u64": draw_u64,
        "selected_index": selected_index,
        "selected_move": temperature_pilot.policy_index_to_gtp(selected_index),
        "policy_sha256": temperature_pilot.policy_digest(policy),
    }


def _validate_generic_sampling_trace(trace, *, manifest_sha256, canonical_matchup_id, pair_attempt, color_index):
    if not isinstance(trace, dict) or set(trace) != temperature_pilot.TRACE_FIELDS:
        raise ValueError("sampling trace shape is invalid")
    identity = _generic_temperature_player_identity(canonical_matchup_id, trace.get("player"))
    if trace.get("temperature") != identity.temperature:
        raise ValueError("sampling trace temperature does not match its generic player")
    expected_draw = _derive_generic_temperature_draw(
        manifest_sha256=manifest_sha256,
        canonical_matchup_id=canonical_matchup_id,
        pair_attempt=pair_attempt,
        color_index=color_index,
        ply=trace.get("ply"),
        player=trace.get("player"),
    )
    if type(trace.get("draw_u64")) is not int or trace["draw_u64"] != expected_draw:
        raise ValueError("sampling trace draw does not match")
    index = trace.get("selected_index")
    if type(index) is not int or not 0 <= index <= BOARD_SIZE * BOARD_SIZE:
        raise ValueError("sampling trace selected index is outside 0..361")
    if trace.get("selected_move") != temperature_pilot.policy_index_to_gtp(index):
        raise ValueError("sampling trace selected move does not match its index")
    if not isinstance(trace.get("policy_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", trace["policy_sha256"]):
        raise ValueError("sampling trace policy digest is invalid")
    return trace


def _temperature_audit_preflight(
    history,
    rung: LadderRung,
    selection: str,
    temperature_context: Optional[Mapping[str, object]],
    sampling_trace: Optional[list],
    player: Optional[str],
):
    required = {
        "protocol_version",
        "manifest_sha256",
        "canonical_matchup_id",
        "pair_attempt",
        "color_index",
        "player",
    }
    if not isinstance(temperature_context, Mapping) or not isinstance(sampling_trace, list):
        raise LadderMoveError("temperature HumanSL requires audit context and sampling trace")
    if set(temperature_context) != required or temperature_context["protocol_version"] not in {
        temperature_pilot.PROTOCOL_VERSION,
        GENERIC_TEMPERATURE_PROTOCOL_VERSION,
    }:
        raise LadderMoveError("temperature HumanSL audit context is incomplete or invalid")
    if player is not None and (player not in {"A", "B"} or temperature_context["player"] != player):
        raise LadderMoveError("temperature HumanSL audit player does not match the move player")
    try:
        generic_protocol = temperature_context["protocol_version"] == GENERIC_TEMPERATURE_PROTOCOL_VERSION
        identity = (
            _generic_temperature_player_identity(
                temperature_context["canonical_matchup_id"], temperature_context["player"]
            )
            if generic_protocol
            else temperature_pilot.matchup_player_identity(
                temperature_context["canonical_matchup_id"], temperature_context["player"]
            )
        )
        if rung.human_sl_profile is None or rung.human_policy_temperature is None:
            raise ValueError("temperature rung is missing its HumanSL profile or local temperature")
        expected_identity = temperature_pilot.temperature_player_identity(
            rung.human_sl_profile, str(rung.human_policy_temperature)
        )
        if identity != expected_identity or selection != expected_identity.selection:
            raise ValueError("temperature player identity does not match the frozen matchup")
        trace_context = {
            key: temperature_context[key]
            for key in ("manifest_sha256", "canonical_matchup_id", "pair_attempt", "color_index")
        }
        derive_draw = _derive_generic_temperature_draw if generic_protocol else temperature_pilot.derive_draw
        draw_u64 = derive_draw(
            **trace_context,
            ply=len(history),
            player=temperature_context["player"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LadderMoveError(f"invalid temperature sampling evidence: {exc}") from exc
    return identity, trace_context, draw_u64


async def _player_move_certified(
    client,
    base_url,
    history,
    *,
    rung: LadderRung,
    selection: str,
    wrn: float,
    capabilities: Mapping[str, object],
    attestations: Optional[list] = None,
    player: Optional[str] = None,
    temperature_context: Optional[Mapping[str, object]] = None,
    sampling_trace: Optional[list] = None,
):
    """Shared attested move implementation; callers define their permitted selection modes."""
    try:
        spec = rung_strength_spec(rung)
        if rung.mechanism == "humansl_search" and dict(rung.human_sl_params) != HUMANSL_PIKL_BASELINE:
            raise LadderMoveError("HumanSL search PIKL settings drifted from the canonical recipe")
        capability_identity = adapters._capability_identity(capabilities, spec)
    except (KeyError, ValueError, LadderMoveError) as exc:
        if isinstance(exc, LadderMoveError):
            raise
        raise LadderMoveError(f"invalid self-play strength specification: {exc}") from exc
    temperature_preflight = None
    if selection == "temperature_weighted":
        temperature_preflight = _temperature_audit_preflight(
            history, rung, selection, temperature_context, sampling_trace, player
        )
    q = adapters.build_ladder_analysis_query(history, rung, BOARD_SIZE, KOMI, RULES, wrn)
    r = await client.post(f"{base_url}/analyze", json=q, timeout=httpx.Timeout(180.0, connect=10.0))
    r.raise_for_status()
    analysis = r.json()

    # Native HumanSL has no explicit route selector, but this experiment harness still requires
    # the wrapper to attest the default main model and its human model before using humanPolicy.
    attested_spec = (
        spec
        if spec.main_model is not None
        else dataclasses.replace(spec, main_model=capability_identity["selected_model"])
    )
    validate_analysis_attestation(analysis, attested_spec, capability_identity)
    if selection == "search":
        picked = pick_ladder_move(analysis, (BOARD_SIZE, BOARD_SIZE), rung.mechanism)
    elif selection == "policy_argmax":
        picked = pick_ladder_rung_move(analysis, rung, (BOARD_SIZE, BOARD_SIZE))
    elif selection == "weighted":
        picked = pick_ladder_move(analysis, (BOARD_SIZE, BOARD_SIZE), "humansl")
    elif selection == "argmax_human":
        hp = analysis.get("humanPolicy")
        if not _valid_policy(hp, BOARD_SIZE * BOARD_SIZE + 1):
            raise LadderMoveError("argmax HumanSL requires a valid humanPolicy")
        picked = _pick_argmax_human(hp, (BOARD_SIZE, BOARD_SIZE))
    elif selection == "temperature_weighted":
        hp = analysis.get("humanPolicy")
        if not _valid_policy(hp, BOARD_SIZE * BOARD_SIZE + 1):
            raise LadderMoveError("temperature HumanSL requires a valid humanPolicy")
        identity, trace_context, draw_u64 = temperature_preflight
        try:
            picked, selected_index = pick_temperature_policy(
                hp, (BOARD_SIZE, BOARD_SIZE), rung.human_policy_temperature, draw_u64
            )
            build_trace = (
                _build_generic_sampling_trace
                if temperature_context["protocol_version"] == GENERIC_TEMPERATURE_PROTOCOL_VERSION
                else temperature_pilot.build_sampling_trace
            )
            trace = build_trace(
                **trace_context,
                ply=len(history),
                player=temperature_context["player"],
                temperature=identity.temperature,
                draw_u64=draw_u64,
                selected_index=selected_index,
                policy=hp,
            )
            validate_trace = (
                _validate_generic_sampling_trace
                if temperature_context["protocol_version"] == GENERIC_TEMPERATURE_PROTOCOL_VERSION
                else temperature_pilot.validate_sampling_trace
            )
            validate_trace(trace, **trace_context)
        except (KeyError, TypeError, ValueError) as exc:
            raise LadderMoveError(f"invalid temperature sampling evidence: {exc}") from exc
        sampling_trace.append(trace)
    else:
        raise LadderMoveError(f"unknown self-play selection {selection!r}")
    if attestations is not None:
        if player not in {"A", "B"}:
            raise ValueError("attested self-play moves require player A or B")
        attestations.append({"ply": len(history), "player": player, "identity": dict(analysis["_wrapper"])})
    return "pass" if picked == "pass" else colrow_to_golaxy(picked[0], picked[1], BOARD_SIZE)


async def player_move_strict(
    client,
    base_url,
    history,
    *,
    rung: LadderRung,
    selection: str,
    wrn: float,
    capabilities: Mapping[str, object],
    attestations: Optional[list] = None,
    player: Optional[str] = None,
    temperature_context: Optional[Mapping[str, object]] = None,
    sampling_trace: Optional[list] = None,
):
    """Return one alignment-safe move, raising ``LadderMoveError`` on any drift."""
    expected_selection = (
        "argmax_human"
        if rung.mechanism == "humansl"
        else "policy_argmax"
        if rung.selection == "native_policy_argmax"
        else "search"
    )
    if selection != expected_selection:
        raise LadderMoveError(f"strict self-play selection drift: expected {expected_selection!r}, got {selection!r}")
    return await _player_move_certified(
        client,
        base_url,
        history,
        rung=rung,
        selection=selection,
        wrn=wrn,
        capabilities=capabilities,
        attestations=attestations,
        player=player,
        temperature_context=temperature_context,
        sampling_trace=sampling_trace,
    )


async def _player_move(
    client,
    base_url,
    history,
    *,
    rung: LadderRung,
    selection: str,
    wrn: float,
    capabilities: Mapping[str, object],
    attestations: Optional[list] = None,
    player: Optional[str] = None,
    temperature_context: Optional[Mapping[str, object]] = None,
    sampling_trace: Optional[list] = None,
):
    """Backward-compatible self-play move wrapper: typed certification failures are unavailable."""
    try:
        return await _player_move_certified(
            client,
            base_url,
            history,
            rung=rung,
            selection=selection,
            wrn=wrn,
            capabilities=capabilities,
            attestations=attestations,
            player=player,
            temperature_context=temperature_context,
            sampling_trace=sampling_trace,
        )
    except LadderMoveError:
        return "unavailable"  # -> harness marks inconclusive_engine (never a fabricated move)


def _fname(label: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "-", label)


def parse_matchups(spec: str, *, experimental_min_humansl_search_visits: int = 40) -> List[Tuple[str, str, int]]:
    """Parse ``A:B:target`` entries where target is fully conclusive color pairs."""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        bits = part.split(":")
        if len(bits) != 3:
            raise ValueError(f"matchup {part!r}: want 'A:B:complete_pairs'")
        a, b, g = bits[0].strip(), bits[1].strip(), int(bits[2])
        make_player(a, experimental_min_humansl_search_visits=experimental_min_humansl_search_visits)
        make_player(b, experimental_min_humansl_search_visits=experimental_min_humansl_search_visits)
        if g <= 0:
            raise ValueError(f"matchup {part!r}: complete pairs must be > 0")
        out.append((a, b, g))
    if not out:
        raise ValueError(f"no matchups parsed from {spec!r}")
    return out


def resolve_boundary_assignment(
    protocol_version: str,
    *,
    phase: str,
    spec_a: str,
    spec_b: str,
    target_pairs: int,
    max_pair_attempts: int,
) -> dict:
    if protocol_version != BOUNDARY_PROTOCOL_VERSION:
        raise ValueError(f"unsupported boundary protocol {protocol_version!r}")
    match = re.fullmatch(r"(rank_[5-8]d)@([0-9]+)", spec_a)
    opponent = re.fullmatch(r"(rank_[6-9]d)@1s", spec_b)
    if not match or not opponent:
        raise ValueError("boundary protocol does not support this matchup")
    transition = f"{match.group(1)}__{opponent.group(1)}"
    if transition not in BOUNDARY_TRANSITIONS:
        raise ValueError("boundary protocol does not support this rank transition")
    visits = int(match.group(2))
    allowed_visits = BOUNDARY_SCREEN_VISITS if phase == "screen" else BOUNDARY_CONFIRM_VISITS
    expected_target = 10 if phase == "screen" else 20
    expected_cap = 20 if phase == "screen" else 40
    if phase not in {"screen", "confirm"} or visits not in allowed_visits:
        raise ValueError("boundary protocol does not support this phase or visit point")
    if target_pairs != expected_target or max_pair_attempts != expected_cap:
        raise ValueError(f"boundary protocol requires target/cap {expected_target}/{expected_cap} for phase {phase}")
    suite, allocation = load_boundary_opening_allocation()
    known, known_digest = load_known_endpoints()
    allocation_key = f"{phase}:{transition}:{visits}"
    assigned_ids = allocation["allocations"][allocation_key]
    by_id = {opening["id"]: opening for opening in suite["openings"]}
    openings = [by_id[opening_id] for opening_id in assigned_ids]
    known_endpoint = next(endpoint for endpoint in known["endpoints"] if endpoint["transition"] == transition)
    source_digest = canonical_manifest_digest(known_endpoint)
    fingerprint = {
        "protocol_version": protocol_version,
        "phase": phase,
        "transition": transition,
        "tested_visits": visits,
        "point_estimate_pass_rule": BOUNDARY_POINT_ESTIMATE_PASS_RULE,
        "finite_grid": list(BOUNDARY_GRID),
        "search_order": BOUNDARY_SEARCH_ORDER,
        "stopping_rule": BOUNDARY_STOPPING_RULE,
        "target_complete_pairs": target_pairs,
        "max_pair_attempts": max_pair_attempts,
        "suite_checksum": suite["checksum"],
        "allocation_digest": allocation["digest"],
        "known_endpoints_digest": known_digest,
        "known_endpoint_source_digest": source_digest,
        "allocation_key": allocation_key,
        "assigned_opening_ids": list(assigned_ids),
        "assigned_opening_sequences": [list(opening["moves"]) for opening in openings],
    }
    return {
        "suite": suite,
        "allocation": allocation,
        "known_endpoints": known,
        "openings": openings,
        "fingerprint": fingerprint,
    }


def _json_value(value):
    """Convert frozen capability mappings to canonical JSON-compatible values."""
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _configuration_fingerprint(configuration: Mapping[str, object]) -> str:
    payload = json.dumps(
        _json_value(configuration), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _preflight_capabilities(capabilities: Mapping[str, object], players: Mapping[str, tuple]) -> dict:
    """Resolve and validate every player route plus the fixed b28 referee before games begin."""
    identities = {}
    try:
        for side in ("A", "B"):
            _label, rung, _selection = players[side]
            identities[side] = dict(adapters._capability_identity(capabilities, rung_strength_spec(rung)))
        _label, referee, _selection = make_player("b28@200")
        identities["referee"] = dict(adapters._capability_identity(capabilities, rung_strength_spec(referee)))
    except (KeyError, LadderMoveError) as exc:
        raise ValueError(f"self-play capability preflight failed: {exc}") from exc
    return identities


def _matchup_configuration(
    players: Mapping[str, tuple],
    identities: Mapping[str, Mapping[str, object]],
    *,
    capabilities: Mapping[str, object],
    wide_root_noise: float,
    target_pairs: int,
    max_pair_attempts: int,
    phase: str = "confirm",
    experiment4: bool = False,
    opening_suite: Optional[Mapping[str, object]] = None,
    experimental_min_humansl_search_visits: int = 40,
    boundary_protocol_version: Optional[str] = None,
    boundary: Optional[Mapping[str, object]] = None,
    boundary_source_snapshot: Optional[Mapping[str, object]] = None,
    exact_openings: Optional[List[Mapping[str, object]]] = None,
    pilot_context: Optional[Mapping[str, object]] = None,
) -> dict:
    if type(experimental_min_humansl_search_visits) is not int or experimental_min_humansl_search_visits < 2:
        raise ValueError("experimental HumanSL search minimum must be a plain int of at least 2")
    if type(target_pairs) is not int or target_pairs <= 0:
        raise ValueError("target complete pairs must be a positive plain int")
    if type(max_pair_attempts) is not int or max_pair_attempts <= 0:
        raise ValueError("maximum pair attempts must be a positive plain int")
    suite = dict(opening_suite or load_opening_suite())
    configured_players = {}
    for side in ("A", "B"):
        label, rung, selection = players[side]
        spec = rung_strength_spec(rung)
        query = adapters.build_ladder_analysis_query([], rung, BOARD_SIZE, KOMI, RULES, wide_root_noise)
        configured_players[side] = {
            "label": label,
            "profile": rung.human_sl_profile,
            "mechanism": rung.mechanism,
            "visits": spec.visits,
            "requested_main_model": spec.main_model,
            "requested_human_model": spec.human_model,
            "effective_overrides": dict(spec.override_settings),
            "http_effective_overrides": query["overrideSettings"],
            "selection": selection,
            "selection_algorithm_version": SELECTION_ALGORITHM_VERSION,
            "identity": dict(identities[side]),
        }
        if pilot_context is not None:
            try:
                pilot_identity = temperature_pilot.matchup_player_identity(pilot_context["canonical_matchup_id"], side)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"pilot selection identity is invalid: {exc}") from exc
            if (
                pilot_identity.canonical_label != label
                or pilot_identity.profile != rung.human_sl_profile
                or pilot_identity.selection != selection
            ):
                raise ValueError("pilot selection identity does not match the configured player")
            configured_players[side]["selection_algorithm_version"] = pilot_identity.selection_algorithm
            if pilot_identity.temperature is not None:
                configured_players[side]["temperature"] = pilot_identity.temperature
    configuration = {
        "capability_schema": capabilities.get("capability_schema"),
        "katago_version": capabilities.get("katago_version"),
        "capability_snapshot": capabilities,
        "boundary_protocol_version": boundary_protocol_version,
        "experimental_min_humansl_search_visits": experimental_min_humansl_search_visits,
        "players": configured_players,
        "game": {
            "board_size": BOARD_SIZE,
            "komi": KOMI,
            "rules": adapters.BaseEngine.get_rules(RULES),
            "move_cap": MOVE_CAP,
        },
        "referee": {
            "visits": REFEREE_VISITS,
            "requested_main_model": "b28",
            "requested_human_model": None,
            "http_effective_overrides": {
                "model": "b28",
                "reportAnalysisWinratesAs": "BLACK",
            },
            "identity": identities["referee"],
        },
        "adjudication_algorithm_version": ADJUDICATION_ALGORITHM_VERSION,
        "wide_root_noise": wide_root_noise,
        "symmetry_settings": SYMMETRY_SETTINGS,
        "phase": phase,
        "experiment4": experiment4,
        "target_complete_pairs": target_pairs,
        "max_pair_attempts": max_pair_attempts,
        "opening_suite": {
            "id": suite["suite_id"],
            "suite_id": suite["suite_id"],
            "seed": suite["seed"],
            "board_size": suite["board_size"],
            "checksum": suite["checksum"],
        },
    }
    if exact_openings is not None:
        configuration["opening_suite"]["cycle"] = False
        configuration["opening_suite"]["allocations"] = [
            {"attempt": attempt, "id": opening["id"], "moves": list(opening["moves"])}
            for attempt, opening in enumerate(exact_openings)
        ]
    if pilot_context is not None:
        configuration["temperature_pilot"] = dict(pilot_context)
    if boundary is not None:
        configuration["boundary"] = dict(boundary)
    if boundary_protocol_version is not None:
        if boundary_source_snapshot is None:
            raise ValueError("boundary configuration requires a validated source snapshot")
        expected_revision = (
            boundary_source_snapshot.get("expected_source_revision")
            if isinstance(boundary_source_snapshot, Mapping)
            else None
        )
        configuration["boundary_source"] = _validate_boundary_source_snapshot(
            boundary_source_snapshot, expected_revision
        )
    elif boundary_source_snapshot is not None:
        raise ValueError("ordinary self-play cannot include a boundary source snapshot")
    return _json_value(configuration)


def _validate_record_attestations(record: Mapping[str, object], configuration: Mapping[str, object]) -> None:
    attestations = record.get("move_attestations")
    if not isinstance(attestations, list):
        raise ValueError("checkpoint game record has no move attestations")
    attested_turn_count = record.get("attested_turn_count")
    if type(attested_turn_count) is not int or attested_turn_count < 0 or len(attestations) != attested_turn_count:
        raise ValueError("checkpoint does not attest every accepted move")
    a_color = record.get("a_color")
    if a_color not in ("B", "W"):
        raise ValueError("checkpoint game record has invalid A color")
    expected_players = configuration.get("players")
    if not isinstance(expected_players, Mapping):
        raise ValueError("checkpoint configuration has no players")
    opening_moves = record.get("opening_moves")
    if not isinstance(opening_moves, list):
        raise ValueError("checkpoint game record has no opening moves")
    opening_length = len(opening_moves)
    for attestation_index, attestation in enumerate(attestations):
        expected_ply = opening_length + attestation_index
        if not isinstance(attestation, Mapping):
            raise ValueError("checkpoint move attestation is malformed")
        side = attestation.get("player")
        if side not in ("A", "B") or type(attestation.get("ply")) is not int or attestation.get("ply") != expected_ply:
            raise ValueError("checkpoint game move attestation has invalid player or ply")
        expected_side = "A" if ((expected_ply % 2 == 0) == (a_color == "B")) else "B"
        if side != expected_side:
            raise ValueError("checkpoint move attestation names the wrong player")
        actual = attestation.get("identity")
        expected_player = expected_players.get(side)
        expected = expected_player.get("identity") if isinstance(expected_player, Mapping) else None
        if not isinstance(actual, Mapping) or not isinstance(expected, Mapping):
            raise ValueError("checkpoint move attestation identity is malformed")
        if any(field not in actual or actual.get(field) != expected.get(field) for field in _IDENTITY_FIELDS):
            raise ValueError("checkpoint move attestation does not match startup capability")


_RESULTS = {
    "our_win",
    "our_loss",
    "inconclusive_score",
    "inconclusive_unsettled",
    "inconclusive_engine",
    "inconclusive_terminal",
}
_END_REASONS = {
    "our_pass",
    "golaxy_pass",
    "golaxy_resign",
    "golaxy_terminal",
    "golaxy_illegal",
    "move_cap",
}


def _validate_game_record(
    record: Mapping[str, object], expected_index: int, configuration: Mapping[str, object]
) -> None:
    players = configuration.get("players")
    if not isinstance(record, Mapping) or not isinstance(players, Mapping):
        raise ValueError("checkpoint game record is malformed")
    required_fields = {
        "record_type",
        "fingerprint",
        "index",
        "player_a",
        "player_b",
        "a_color",
        "our_color",
        "result",
        "our_win",
        "num_moves",
        "black_score",
        "conclusive",
        "end_reason",
        "attested_turn_count",
        "move_attestations",
        "phase",
        "opening_id",
        "opening_moves",
        "pair_attempt",
        "color_index",
        "ts",
    }
    if not required_fields.issubset(record):
        raise ValueError("checkpoint game record is missing required fields")
    color_index = record.get("color_index")
    expected_color = "B" if color_index == 0 else "W"
    if type(record.get("index")) is not int or record.get("index") != expected_index:
        raise ValueError("checkpoint game indices must be unique, ordered, and gap-free")
    if record.get("a_color") != expected_color or record.get("our_color") != expected_color:
        raise ValueError("checkpoint game color parity is invalid")
    if record.get("phase") != configuration.get("phase"):
        raise ValueError("checkpoint game phase does not match the header")
    if (
        type(record.get("pair_attempt")) is not int
        or record.get("pair_attempt") < 0
        or type(color_index) is not int
        or color_index not in {0, 1}
        or record.get("index") != 2 * record.get("pair_attempt") + color_index
    ):
        raise ValueError("checkpoint game pair key is malformed")
    if not isinstance(record.get("opening_id"), str) or not isinstance(record.get("opening_moves"), list):
        raise ValueError("checkpoint game opening is malformed")
    if record.get("player_a") != players["A"]["label"] or record.get("player_b") != players["B"]["label"]:
        raise ValueError("checkpoint game player labels do not match the header")
    result = record.get("result")
    our_win = record.get("our_win")
    conclusive = record.get("conclusive")
    num_moves = record.get("num_moves")
    black_score = record.get("black_score")
    end_reason = record.get("end_reason")
    timestamp = record.get("ts")
    if (
        not isinstance(result, str)
        or result not in _RESULTS
        or type(our_win) is not bool
        or type(conclusive) is not bool
    ):
        raise ValueError("checkpoint game outcome fields are malformed")
    if type(num_moves) is not int or num_moves < 0:
        raise ValueError("checkpoint game num_moves is malformed")
    if black_score is not None and (
        isinstance(black_score, bool) or not isinstance(black_score, (int, float)) or not math.isfinite(black_score)
    ):
        raise ValueError("checkpoint game black_score is malformed")
    if not isinstance(end_reason, str) or end_reason not in _END_REASONS:
        raise ValueError("checkpoint game end_reason is malformed")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
        raise ValueError("checkpoint game timestamp is malformed")
    expected_conclusive = result in {"our_win", "our_loss"}
    if conclusive != expected_conclusive or our_win != (result == "our_win"):
        raise ValueError("checkpoint game result flags are inconsistent")
    _validate_record_attestations(record, configuration)
    accepted_pass = end_reason in {"our_pass", "golaxy_pass"} and result != "inconclusive_engine"
    opening_length = len(record["opening_moves"])
    if num_moves < opening_length:
        raise ValueError("checkpoint game num_moves is shorter than its opening")
    expected_attested = num_moves - opening_length + (1 if accepted_pass else 0)
    if record.get("attested_turn_count") != expected_attested:
        raise ValueError("checkpoint game attested turn count is inconsistent with its ending")
    pilot_context = configuration.get("temperature_pilot")
    temperature_players = {side for side in ("A", "B") if players[side].get("selection") == "temperature_weighted"}
    if temperature_players:
        traces = record.get("sampling_trace")
        if not isinstance(traces, list):
            raise ValueError("temperature checkpoint game has no sampling trace")
        expected_temperature_turns = [
            (attestation["ply"], attestation["player"])
            for attestation in record["move_attestations"]
            if attestation["player"] in temperature_players
        ]
        if [
            (trace.get("ply"), trace.get("player")) for trace in traces if isinstance(trace, Mapping)
        ] != expected_temperature_turns:
            raise ValueError("checkpoint sampling trace does not cover exactly the temperature-selected turns")
        trace_seed = pilot_context["manifest_sha256"] if pilot_context is not None else record["fingerprint"]
        canonical_matchup_id = (
            pilot_context["canonical_matchup_id"]
            if pilot_context is not None
            else f"{players['A']['label']}__vs__{players['B']['label']}"
        )
        for trace in traces:
            try:
                validate_trace = (
                    temperature_pilot.validate_sampling_trace
                    if pilot_context is not None
                    else _validate_generic_sampling_trace
                )
                validate_trace(
                    trace,
                    # The existing trace schema calls this manifest_sha256. Generic runs use the
                    # checkpoint configuration fingerprint as the compatible deterministic seed.
                    manifest_sha256=trace_seed,
                    canonical_matchup_id=canonical_matchup_id,
                    pair_attempt=record["pair_attempt"],
                    color_index=record["color_index"],
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"checkpoint sampling trace is invalid: {exc}") from exc


def _validate_checkpoint_byte_bounds(data: bytes) -> bytes:
    if len(data) > PILOT_CHECKPOINT_MAX_BYTES:
        raise ValueError("pilot checkpoint exceeds total byte limit")
    line_start = 0
    for index, byte in enumerate(data):
        if byte == 0x0A:
            if index + 1 - line_start > PILOT_CHECKPOINT_MAX_LINE_BYTES:
                raise ValueError("pilot checkpoint exceeds per-line byte limit")
            line_start = index + 1
    if len(data) - line_start > PILOT_CHECKPOINT_MAX_LINE_BYTES:
        raise ValueError("pilot checkpoint exceeds per-line byte limit")
    return data


def _read_bounded_checkpoint(path: Path) -> bytes:
    try:
        if path.stat().st_size > PILOT_CHECKPOINT_MAX_BYTES:
            raise ValueError("pilot checkpoint exceeds total byte limit")
        with path.open("rb") as checkpoint:
            data = checkpoint.read(PILOT_CHECKPOINT_MAX_BYTES + 1)
    except OSError as exc:
        raise ValueError(f"cannot read self-play checkpoint: {exc}") from exc
    return _validate_checkpoint_byte_bounds(data)


def _validated_checkpoint_records(data: bytes, fingerprint: str, configuration: Mapping[str, object]) -> List[dict]:
    records = _parse_strict_jsonl(data, context="self-play checkpoint game stream")
    if not records:
        raise ValueError(f"checkpoint exists without a schema-{CHECKPOINT_SCHEMA} header")
    header = records[0]
    if header.get("record_type") != "header" or header.get("schema") != CHECKPOINT_SCHEMA:
        raise ValueError(f"checkpoint has no schema-{CHECKPOINT_SCHEMA} header")
    if header.get("fingerprint") != fingerprint:
        raise ValueError("checkpoint header fingerprint does not match this run")
    if _configuration_fingerprint(header.get("configuration", {})) != fingerprint:
        raise ValueError("checkpoint header configuration does not match its fingerprint")
    if _json_value(header.get("configuration")) != _json_value(configuration):
        raise ValueError("checkpoint header configuration does not match this run")
    for expected_index, record in enumerate(records[1:]):
        if record.get("record_type") != "game":
            raise ValueError("checkpoint contains an unexpected record type")
        if record.get("fingerprint") != fingerprint:
            raise ValueError("checkpoint game fingerprint does not match this run")
        _validate_game_record(record, expected_index, configuration)
    return records


def _read_checkpoint_snapshot(path: Path, *, pilot: bool) -> bytes:
    if pilot:
        return _read_bounded_checkpoint(path)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read self-play checkpoint: {exc}") from exc


def _already_done(path: Path, fingerprint: str, configuration: Mapping[str, object]) -> int:
    if configuration.get("temperature_pilot") is not None:
        if not _pilot_checkpoint_exists(path):
            return 0
        data = _read_checkpoint_snapshot(path, pilot=True)
    else:
        if not path.is_file():
            return 0
        data = _read_checkpoint_snapshot(path, pilot=False)
    records = _validated_checkpoint_records(data, fingerprint, configuration)
    return len(records) - 1


def _pilot_checkpoint_exists(path: Path) -> bool:
    try:
        status = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ValueError(f"cannot inspect pilot checkpoint: {exc}") from exc
    if not stat_module.S_ISREG(status.st_mode):
        raise ValueError("pilot checkpoint occupant must be a regular file, not a symlink or special file")
    return True


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_replace_checkpoint(path: Path, data: bytes) -> None:
    _validate_checkpoint_byte_bounds(data)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_create_checkpoint(path: Path, data: bytes) -> None:
    _validate_checkpoint_byte_bounds(data)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
        _fsync_directory(path.parent)


def _prepare_checkpoint(
    path: Path, fingerprint: str, configuration: Mapping[str, object], *, atomic: bool = False
) -> int:
    if (atomic and _pilot_checkpoint_exists(path)) or (not atomic and path.exists()):
        return _already_done(path, fingerprint, configuration)
    header = {
        "record_type": "header",
        "schema": CHECKPOINT_SCHEMA,
        "fingerprint": fingerprint,
        "configuration": _json_value(configuration),
    }
    encoded = (json.dumps(header, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    if atomic:
        try:
            _atomic_create_checkpoint(path, encoded)
        except FileExistsError:
            return _already_done(path, fingerprint, configuration)
    else:
        with path.open("x") as f:
            f.write(encoded.decode("utf-8"))
            f.flush()
    return 0


@contextmanager
def _checkpoint_lock(path: Path):
    """Hold a non-blocking process lock for one checkpoint's complete validate/append run."""
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("a+b")
    locked = False
    try:
        try:
            if _fcntl is not None:
                _fcntl.flock(lock_file.fileno(), _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            elif _msvcrt is not None:
                lock_file.seek(0, os.SEEK_END)
                if lock_file.tell() == 0:
                    lock_file.write(b"\0")
                    lock_file.flush()
                lock_file.seek(0)
                _msvcrt.locking(lock_file.fileno(), _msvcrt.LK_NBLCK, 1)
            else:  # unsupported Python/platform build
                raise RuntimeError("no supported checkpoint locking backend (need fcntl or msvcrt)")
            locked = True
        except (BlockingIOError, OSError) as exc:
            raise RuntimeError(f"self-play checkpoint is locked by another process: {path}") from exc
        yield
    finally:
        try:
            if locked and _fcntl is not None:
                _fcntl.flock(lock_file.fileno(), _fcntl.LOCK_UN)
            elif locked and _msvcrt is not None:
                lock_file.seek(0)
                _msvcrt.locking(lock_file.fileno(), _msvcrt.LK_UNLCK, 1)
        finally:
            lock_file.close()


def _validated_out_dir(path: Path) -> Path:
    path = Path(path)
    if path.resolve() == LEGACY_OUT_DIR.resolve():
        raise ValueError(f"legacy self-play results cannot be resumed; use the fresh namespace {DEFAULT_OUT_DIR}")
    return path


async def run_matchup(
    specA: str,
    specB: str,
    target_pairs: int,
    *,
    client: httpx.AsyncClient,
    base_url: str,
    wrn: float,
    out_dir: Path,
    capabilities: Mapping[str, object],
    phase: str = "confirm",
    experiment4: bool = False,
    max_pair_attempts: Optional[int] = None,
    experimental_min_humansl_search_visits: int = 40,
    boundary_protocol: Optional[str] = None,
    expected_source_revision: Optional[str] = None,
    boundary_source_snapshot: Optional[Mapping[str, object]] = None,
    exact_openings: Optional[List[Mapping[str, object]]] = None,
    pilot_context: Optional[Mapping[str, object]] = None,
) -> dict:
    required = required_conclusive_pairs(phase, experiment4=experiment4)
    if type(target_pairs) is not int or target_pairs < required or (phase == "screen" and target_pairs != required):
        comparator = "exactly" if phase == "screen" else "at least"
        raise ValueError(f"{phase} target must be {comparator} {required} fully conclusive pairs")
    if max_pair_attempts is None:
        max_pair_attempts = max(target_pairs * 2, target_pairs + 10)
    elif type(max_pair_attempts) is not int or max_pair_attempts <= 0:
        raise ValueError("maximum pair attempts must be a positive plain int")
    if (exact_openings is None) != (pilot_context is None):
        raise ValueError("exact openings and pilot context must be supplied together")
    boundary_inputs = None
    if boundary_protocol is not None:
        if boundary_source_snapshot is None:
            boundary_source_snapshot = load_boundary_source_snapshot(expected_source_revision)
        else:
            boundary_source_snapshot = _validate_boundary_source_snapshot(
                boundary_source_snapshot, expected_source_revision
            )
        out_dir = validate_boundary_out_dir(out_dir, boundary_source_snapshot)
        boundary_inputs = resolve_boundary_assignment(
            boundary_protocol,
            phase=phase,
            spec_a=specA,
            spec_b=specB,
            target_pairs=target_pairs,
            max_pair_attempts=max_pair_attempts,
        )
        opening_suite = boundary_inputs["suite"]
        openings = boundary_inputs["openings"]
    elif exact_openings is not None:
        if expected_source_revision is not None or boundary_source_snapshot is not None:
            raise ValueError("pilot exact openings cannot include boundary source arguments")
        required_context_fields = {
            "protocol_version",
            "manifest_path",
            "manifest_sha256",
            "canonical_matchup_id",
            "launch_snapshot_sha256",
        }
        if not isinstance(pilot_context, Mapping) or set(pilot_context) != required_context_fields:
            raise ValueError("pilot context shape is invalid")
        if pilot_context.get("protocol_version") != temperature_pilot.PROTOCOL_VERSION:
            raise ValueError("pilot context protocol is invalid")
        for digest_field in ("manifest_sha256", "launch_snapshot_sha256"):
            digest = pilot_context.get(digest_field)
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"pilot context {digest_field} is invalid")
        opening_suite = load_opening_suite()
        openings = [dict(opening) for opening in exact_openings]
    else:
        if expected_source_revision is not None or boundary_source_snapshot is not None:
            raise ValueError("--expected-source-revision is only valid with --boundary-protocol")
        opening_suite = load_opening_suite()
        openings = opening_suite["openings"]
    playerA = make_player(specA, experimental_min_humansl_search_visits=experimental_min_humansl_search_visits)
    playerB = make_player(specB, experimental_min_humansl_search_visits=experimental_min_humansl_search_visits)
    labelA, rungA, selA = playerA
    labelB, rungB, selB = playerB
    players = {"A": playerA, "B": playerB}
    if pilot_context is not None and pilot_context["canonical_matchup_id"] != f"{labelA}__vs__{labelB}":
        raise ValueError("pilot context matchup identity does not match the players")
    identities = _preflight_capabilities(capabilities, players)
    configuration = _matchup_configuration(
        players,
        identities,
        capabilities=capabilities,
        wide_root_noise=wrn,
        target_pairs=target_pairs,
        max_pair_attempts=max_pair_attempts,
        phase=phase,
        experiment4=experiment4,
        opening_suite=opening_suite,
        experimental_min_humansl_search_visits=experimental_min_humansl_search_visits,
        boundary_protocol_version=boundary_protocol,
        boundary=boundary_inputs["fingerprint"] if boundary_inputs else None,
        boundary_source_snapshot=boundary_source_snapshot,
        exact_openings=openings if exact_openings is not None else None,
        pilot_context=pilot_context,
    )
    fingerprint = _configuration_fingerprint(configuration)
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt = out_dir / f"selfplay_{phase}_{_fname(labelA)}__vs__{_fname(labelB)}.jsonl"
    with _checkpoint_lock(ckpt):
        return await _run_matchup_checkpoint(
            labelA=labelA,
            rungA=rungA,
            selA=selA,
            labelB=labelB,
            rungB=rungB,
            selB=selB,
            target_pairs=target_pairs,
            max_pair_attempts=max_pair_attempts,
            phase=phase,
            experiment4=experiment4,
            openings=openings,
            cycle_openings=boundary_inputs is None and exact_openings is None,
            client=client,
            base_url=base_url,
            wrn=wrn,
            capabilities=capabilities,
            configuration=configuration,
            fingerprint=fingerprint,
            ckpt=ckpt,
            pilot_context=pilot_context,
        )


async def _run_matchup_checkpoint(
    *,
    labelA,
    rungA,
    selA,
    labelB,
    rungB,
    selB,
    target_pairs,
    max_pair_attempts,
    phase,
    experiment4,
    openings,
    cycle_openings,
    client,
    base_url,
    wrn,
    capabilities,
    configuration,
    fingerprint,
    ckpt,
    pilot_context=None,
) -> dict:
    pilot_mode = pilot_context is not None
    _prepare_checkpoint(ckpt, fingerprint, configuration, atomic=pilot_mode)
    records = []
    reason_counts: dict = {}
    checkpoint_bytes = b""
    if ckpt.is_file():
        checkpoint_bytes = _read_checkpoint_snapshot(ckpt, pilot=pilot_mode)
        checkpoint_records = _validated_checkpoint_records(checkpoint_bytes, fingerprint, configuration)
        for rec in checkpoint_records:
            if rec.get("record_type") == "header":
                continue
            records.append(rec)
            reason_counts[rec["result"]] = reason_counts.get(rec["result"], 0) + 1
    existing_sample = complete_pair_sample(records, phase=phase)
    if existing_sample["complete_pairs"] > target_pairs:
        raise ValueError(
            f"requested target {target_pairs} is smaller than existing complete pair count "
            f"{existing_sample['complete_pairs']}"
        )

    adj = partial(
        adapters.adjudicate,
        client,
        base_url,
        board_size=BOARD_SIZE,
        komi=KOMI,
        rules=RULES,
        visits=REFEREE_VISITS,
        capabilities=capabilities,
    )
    append_file = None if pilot_mode else ckpt.open("a")
    try:
        scheduled = schedule_pair_games(
            records,
            openings,
            phase=phase,
            max_pair_attempts=max_pair_attempts,
            cycle_openings=cycle_openings,
        )
        for scheduled_game in scheduled:
            sample = complete_pair_sample(records, phase=phase)
            if sample["complete_pairs"] >= target_pairs:
                break
            i = 2 * scheduled_game["pair_attempt"] + scheduled_game["color_index"]
            a_color = scheduled_game["a_color"]
            initial_history = scheduled_game["initial_history"]
            move_attestations = []
            temperature_mode = selA == "temperature_weighted" or selB == "temperature_weighted"
            sampling_trace = [] if temperature_mode else None

            def selection_context(player):
                if not temperature_mode:
                    return None
                return {
                    "protocol_version": (
                        pilot_context["protocol_version"]
                        if pilot_context is not None
                        else GENERIC_TEMPERATURE_PROTOCOL_VERSION
                    ),
                    # Compatibility: generic runs seed the existing pilot trace schema with the
                    # checkpoint configuration fingerprint in its manifest_sha256 field.
                    "manifest_sha256": pilot_context["manifest_sha256"] if pilot_context is not None else fingerprint,
                    "canonical_matchup_id": (
                        pilot_context["canonical_matchup_id"]
                        if pilot_context is not None
                        else f"{labelA}__vs__{labelB}"
                    ),
                    "pair_attempt": scheduled_game["pair_attempt"],
                    "color_index": scheduled_game["color_index"],
                    "player": player,
                }

            async def a_move(history):
                return await _player_move(
                    client,
                    base_url,
                    history,
                    rung=rungA,
                    selection=selA,
                    wrn=wrn,
                    capabilities=capabilities,
                    attestations=move_attestations,
                    player="A",
                    temperature_context=selection_context("A"),
                    sampling_trace=sampling_trace,
                )

            async def b_move(history):
                return await _player_move(
                    client,
                    base_url,
                    history,
                    rung=rungB,
                    selection=selB,
                    wrn=wrn,
                    capabilities=capabilities,
                    attestations=move_attestations,
                    player="B",
                    temperature_context=selection_context("B"),
                    sampling_trace=sampling_trace,
                )

            # A occupies play_one_game's "our" slot, B the "golaxy" slot; both return int|'pass'|
            # 'unavailable' only (never resign/terminal/illegal), so the loop scores them normally.
            outcome: GameOutcome = await play_one_game(
                our_move=a_move,
                golaxy_move=b_move,
                adjudicate=adj,
                our_color=a_color,
                board_size=BOARD_SIZE,
                move_cap=MOVE_CAP,
                initial_history=initial_history,
            )
            reason_counts[outcome.result] = reason_counts.get(outcome.result, 0) + 1
            rec = {
                "record_type": "game",
                "fingerprint": fingerprint,
                "index": i,
                "player_a": labelA,
                "player_b": labelB,
                "a_color": a_color,
                "phase": phase,
                "opening_id": scheduled_game["opening_id"],
                "opening_moves": list(initial_history),
                "pair_attempt": scheduled_game["pair_attempt"],
                "color_index": scheduled_game["color_index"],
                **dataclasses.asdict(outcome),  # result/our_win(=A won)/num_moves/black_score/conclusive/end_reason
                "attested_turn_count": len(move_attestations),
                "move_attestations": move_attestations,
                "ts": time.time(),
            }
            if sampling_trace is not None:
                rec["sampling_trace"] = sampling_trace
            encoded_record = (json.dumps(rec, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
            if pilot_mode:
                next_checkpoint_bytes = checkpoint_bytes + encoded_record
                _validate_checkpoint_byte_bounds(next_checkpoint_bytes)
                _atomic_replace_checkpoint(ckpt, next_checkpoint_bytes)
                checkpoint_bytes = next_checkpoint_bytes
            else:
                append_file.write(encoded_record.decode("utf-8"))
                append_file.flush()
            records.append(rec)
            log.info(
                "  %s vs %s game %d/%d: A_%s (%s, end=%s, conclusive=%s, moves=%d, score=%s)",
                labelA,
                labelB,
                i + 1,
                2 * max_pair_attempts,
                "win" if (outcome.conclusive and outcome.our_win) else ("loss" if outcome.conclusive else "?"),
                outcome.result,
                outcome.end_reason,
                outcome.conclusive,
                outcome.num_moves,
                outcome.black_score,
            )
    finally:
        if append_file is not None:
            append_file.close()

    sample = complete_pair_sample(records, phase=phase)
    winsA, conclusive = sample["a_wins"], sample["games"]
    elo, lo, hi = elo_from_winrate(winsA, conclusive)
    if not conclusive:
        lo = hi = None
    interval = list(wilson_interval(winsA, conclusive)) if conclusive else [0.0, 1.0]
    attempted = 1 + max((record["pair_attempt"] for record in records), default=-1)
    target_reached = sample["complete_pairs"] == target_pairs
    classification = (
        classify_seam(winsA, conclusive, experiment4=experiment4)
        if phase == "confirm" and target_reached
        else "screen_complete" if phase == "screen" and target_reached else "insufficient_pairs"
    )
    summary = {
        "player_a": labelA,
        "player_b": labelB,
        "phase": phase,
        "target_complete_pairs": target_pairs,
        "complete_pairs": sample["complete_pairs"],
        "decision_games": conclusive,
        "pair_attempts": attempted,
        "inconclusive_pairs": sample["inconclusive_pairs"],
        "max_pair_attempts": max_pair_attempts,
        "max_attempts_reached": sample["complete_pairs"] < target_pairs and attempted >= max_pair_attempts,
        "conclusive": conclusive,
        "a_wins": winsA,
        "a_winrate": (winsA / conclusive if conclusive else None),
        "a_elo_vs_b": elo,
        "a_elo_ci95": [lo, hi],
        "wilson_ci95": interval,
        "classification": classification,
        "reason_counts": reason_counts,
    }
    log.info(
        "=== %s vs %s: A %d/%d (%.0f%%) Elo %+.0f [%s,%s] ===",
        labelA,
        labelB,
        winsA,
        conclusive,
        100 * (winsA / conclusive) if conclusive else 0.0,
        elo,
        lo,
        hi,
    )
    return summary


async def main_async(args) -> int:
    matchups = parse_matchups(
        args.matchups,
        experimental_min_humansl_search_visits=args.experimental_min_humansl_search_visits,
    )
    if args.boundary_protocol is not None:
        boundary_source_snapshot = load_boundary_source_snapshot(args.expected_source_revision)
        requested_out_dir = validate_boundary_out_dir(Path(args.out), boundary_source_snapshot)
    else:
        if args.expected_source_revision is not None:
            raise ValueError("--expected-source-revision is only valid with --boundary-protocol")
        boundary_source_snapshot = None
        requested_out_dir = Path(args.out)
    if args.wide_root_noise is None:
        wrn = adapters.load_engine_wide_root_noise(
            dict(_MockKaTrainForConfig(force_package_config=True).config("engine"))
        )
        log.info("wide_root_noise = %.4f (from this checkout's config.json engine block)", wrn)
    else:
        wrn = args.wide_root_noise
        log.info("wide_root_noise = %.4f (override)", wrn)
    out_dir = _validated_out_dir(requested_out_dir)
    summaries = []
    async with httpx.AsyncClient() as client:
        capabilities = await adapters.fetch_health_snapshot(client, args.base_url)
        for a, b, g in matchups:
            summaries.append(
                await run_matchup(
                    a,
                    b,
                    g,
                    client=client,
                    base_url=args.base_url,
                    wrn=wrn,
                    out_dir=out_dir,
                    capabilities=capabilities,
                    phase=args.phase,
                    experiment4=args.experiment4,
                    max_pair_attempts=args.max_pair_attempts,
                    experimental_min_humansl_search_visits=args.experimental_min_humansl_search_visits,
                    boundary_protocol=args.boundary_protocol,
                    expected_source_revision=args.expected_source_revision,
                    boundary_source_snapshot=boundary_source_snapshot,
                )
            )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "selfplay_summary.json").write_text(
        json.dumps(
            {"matchups": summaries, "wide_root_noise": wrn},
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    log.info("wrote %s", out_dir / "selfplay_summary.json")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--matchups",
        required=True,
        help="'A:B:complete_pairs,...' e.g. 'rank_9d@80:rank_9d@40:20' (pairs, not games/attempts)",
    )
    p.add_argument("--base-url", default="http://127.0.0.1:8000", help="our KataGo HTTP analysis server")
    p.add_argument("--out", default=str(DEFAULT_OUT_DIR), help="checkpoint dir")
    p.add_argument(
        "--wide-root-noise", type=float, default=None, help="override wideRootNoise (default: shipping config)"
    )
    p.add_argument("--phase", choices=("screen", "confirm"), default="confirm")
    p.add_argument("--experiment4", action="store_true", help="apply the 40-complete-pair experiment-4 threshold")
    p.add_argument("--max-pair-attempts", type=int, default=None, help="separate guard including inconclusive pairs")
    p.add_argument(
        "--experimental-min-humansl-search-visits",
        type=int,
        default=40,
        help="explicit HumanSL-search visit floor for operator-run experiments (default: 40; minimum: 2)",
    )
    p.add_argument(
        "--boundary-protocol",
        choices=(BOUNDARY_PROTOCOL_VERSION,),
        default=None,
        help="enable the frozen HumanSL boundary protocol and exact opening assignment",
    )
    p.add_argument(
        "--expected-source-revision",
        default=None,
        help="required full 40-hex git commit for a boundary-protocol launch",
    )
    return p


def main() -> int:
    return asyncio.run(main_async(build_arg_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
