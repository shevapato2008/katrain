"""Pure protocol primitives for the preregistered HumanSL temperature pilot."""

from __future__ import annotations

import hashlib
import json
import math
import re
import struct
import subprocess
from pathlib import Path
from typing import Iterable, Mapping

from katrain.core.ladder import policy_index_to_gtp


PROTOCOL_VERSION = "humansl-temperature-pilot-v1"
MANIFEST_SCHEMA_VERSION = 1
SELECTION_ALGORITHM_VERSION = "temperature-inverse-cdf-v1"
ARGMAX_SELECTION_ALGORITHM_VERSION = "policy-argmax-v1"
DRAW_ALGORITHM_VERSION = "temperature-draw-sha256-u64-v1"
OPENING_SUITE_PATH = "superpowers/tracks/golaxy-ai-ladder-parity/calibration/opening_suite_v1.json"
RUNTIME_SOURCE_PATHS = (
    "katrain/core/ladder.py",
    "katrain/core/ladder_calibration.py",
    "superpowers/tracks/golaxy-ai-ladder-parity/calibration/adapters.py",
    "superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py",
    "superpowers/tracks/golaxy-ai-ladder-parity/calibration/temperature_pilot.py",
    "superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_temperature_pilot.py",
)
TRACE_FIELDS = frozenset(
    {"ply", "player", "temperature", "draw_u64", "selected_index", "selected_move", "policy_sha256"}
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_TEMPERATURE_RE = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
_WILSON_Z95 = 1.959963984540054


def _temperature_identity(profile: str, temperature: str) -> dict:
    return {
        "canonical_label": f"{profile}@1t{temperature}",
        "profile": profile,
        "selection_algorithm": SELECTION_ALGORITHM_VERSION,
        "temperature": temperature,
    }


def _argmax_identity(profile: str) -> dict:
    return {
        "canonical_label": f"{profile}@1s",
        "profile": profile,
        "selection_algorithm": ARGMAX_SELECTION_ALGORITHM_VERSION,
    }


def _matchup(profile: str, a: Mapping[str, object], b: Mapping[str, object]) -> dict:
    return {
        "matchup_id": f"{a['canonical_label']}__vs__{b['canonical_label']}",
        "profile": profile,
        "a": dict(a),
        "b": dict(b),
        "expected_stronger": "A",
        "phase": "screen",
        "target_complete_pairs": 10,
        "max_pair_attempts": 20,
    }


MATCHUPS = tuple(
    matchup
    for profile in ("rank_1d", "rank_5d", "rank_9d")
    for matchup in (
        _matchup(profile, _temperature_identity(profile, "1"), _temperature_identity(profile, "2")),
        _matchup(profile, _temperature_identity(profile, "0.4"), _temperature_identity(profile, "1")),
        _matchup(profile, _argmax_identity(profile), _temperature_identity(profile, "0.4")),
    )
)


def _plain_nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def canonical_digest(payload: Mapping[str, object], *, exclude: str | None = None) -> str:
    """SHA-256 of canonical JSON, optionally omitting one top-level self-digest field."""
    if not isinstance(payload, Mapping):
        raise ValueError("canonical digest payload must be a mapping")
    canonical = {key: value for key, value in payload.items() if key != exclude}
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def derive_draw(
    *,
    manifest_sha256: str,
    canonical_matchup_id: str,
    pair_attempt: int,
    color_index: int,
    ply: int,
    player: str,
    include_audit: bool = False,
):
    """Derive one stateless unsigned 64-bit draw from the exact protocol JSON array."""
    if not isinstance(manifest_sha256, str) or not _SHA256_RE.fullmatch(manifest_sha256):
        raise ValueError("manifest_sha256 must be a lowercase SHA-256 digest")
    if (
        not isinstance(canonical_matchup_id, str)
        or canonical_matchup_id.count("__vs__") != 1
        or any(not label for label in canonical_matchup_id.split("__vs__"))
    ):
        raise ValueError("canonical_matchup_id is invalid")
    if not _plain_nonnegative_int(pair_attempt):
        raise ValueError("pair_attempt must be a non-negative plain integer")
    if type(color_index) is not int or color_index not in (0, 1):
        raise ValueError("color_index must be 0 or 1")
    if not _plain_nonnegative_int(ply):
        raise ValueError("ply must be a non-negative plain integer")
    if player not in ("A", "B"):
        raise ValueError("player must be A or B")
    payload = [
        PROTOCOL_VERSION,
        manifest_sha256,
        canonical_matchup_id,
        pair_attempt,
        color_index,
        ply,
        player,
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    digest_bytes = hashlib.sha256(encoded).digest()
    draw = int.from_bytes(digest_bytes[:8], "big", signed=False)
    return (encoded, digest_bytes.hex(), draw) if include_audit else draw


def policy_digest(policy: Iterable[object]) -> str:
    """Bind a policy vector as a count followed by big-endian IEEE-754 binary64 values."""
    try:
        values = list(policy)
        encoded = bytearray(struct.pack(">I", len(values)))
        for value in values:
            encoded.extend(struct.pack(">d", float(value)))
    except (TypeError, ValueError, OverflowError, struct.error) as exc:
        raise ValueError(f"policy cannot be encoded as binary64: {exc}") from exc
    return hashlib.sha256(encoded).hexdigest()


def build_sampling_trace(
    *,
    manifest_sha256: str,
    canonical_matchup_id: str,
    pair_attempt: int,
    color_index: int,
    ply: int,
    player: str,
    temperature: str,
    draw_u64: int,
    selected_index: int,
    policy: Iterable[object],
) -> dict:
    if not isinstance(temperature, str) or not _TEMPERATURE_RE.fullmatch(temperature):
        raise ValueError("temperature must be a canonical decimal string")
    expected_draw = derive_draw(
        manifest_sha256=manifest_sha256,
        canonical_matchup_id=canonical_matchup_id,
        pair_attempt=pair_attempt,
        color_index=color_index,
        ply=ply,
        player=player,
    )
    if type(draw_u64) is not int or draw_u64 != expected_draw:
        raise ValueError("draw_u64 does not match the stateless draw")
    move = policy_index_to_gtp(selected_index)
    return {
        "ply": ply,
        "player": player,
        "temperature": temperature,
        "draw_u64": draw_u64,
        "selected_index": selected_index,
        "selected_move": move,
        "policy_sha256": policy_digest(policy),
    }


def validate_sampling_trace(
    trace: object,
    *,
    manifest_sha256: str,
    canonical_matchup_id: str,
    pair_attempt: int,
    color_index: int,
) -> dict:
    """Validate compact trace integrity without claiming to replay the historical inverse CDF."""
    if not isinstance(trace, dict) or set(trace) != TRACE_FIELDS:
        raise ValueError("sampling trace shape is invalid")
    if not _plain_nonnegative_int(trace["ply"]) or trace["player"] not in ("A", "B"):
        raise ValueError("sampling trace shape has invalid ply or player")
    if not isinstance(trace["temperature"], str) or not _TEMPERATURE_RE.fullmatch(trace["temperature"]):
        raise ValueError("sampling trace shape has invalid temperature")
    expected_draw = derive_draw(
        manifest_sha256=manifest_sha256,
        canonical_matchup_id=canonical_matchup_id,
        pair_attempt=pair_attempt,
        color_index=color_index,
        ply=trace["ply"],
        player=trace["player"],
    )
    if type(trace["draw_u64"]) is not int or trace["draw_u64"] != expected_draw:
        raise ValueError("sampling trace draw does not match")
    index = trace["selected_index"]
    if type(index) is not int or not 0 <= index <= 361:
        raise ValueError("sampling trace selected index is outside 0..361")
    if trace["selected_move"] != policy_index_to_gtp(index):
        raise ValueError("sampling trace selected move does not match its index")
    if not isinstance(trace["policy_sha256"], str) or not _SHA256_RE.fullmatch(trace["policy_sha256"]):
        raise ValueError("sampling trace policy digest is invalid")
    return trace


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo_root: Path, *arguments: str) -> str:
    try:
        return subprocess.run(
            ["git", *arguments], cwd=repo_root, check=True, text=True, capture_output=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"git validation failed: {exc}") from exc


def _validate_base_ancestry(repo_root: Path, implementation_base_revision: str) -> str:
    base = _git(repo_root, "rev-parse", "--verify", f"{implementation_base_revision}^{{commit}}")
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", base, "HEAD"],
            cwd=repo_root,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ValueError("implementation base is not an ancestor of HEAD") from exc
    return base


def _load_opening_binding(repo_root: Path) -> dict:
    suite_path = repo_root / OPENING_SUITE_PATH
    try:
        suite = json.loads(suite_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load opening suite: {exc}") from exc
    if not isinstance(suite, dict) or suite.get("suite_id") != "humansl-opening-suite-v1":
        raise ValueError("opening suite identity is invalid")
    if suite.get("checksum") != canonical_digest(suite, exclude="checksum"):
        raise ValueError("opening suite internal checksum mismatch")
    openings = suite.get("openings")
    if not isinstance(openings, list) or len(openings) < 20:
        raise ValueError("opening suite must contain at least 20 entries")
    allocations = []
    seen_ids = set()
    for attempt, opening in enumerate(openings[:20]):
        if (
            not isinstance(opening, dict)
            or set(opening) != {"id", "moves"}
            or not isinstance(opening["id"], str)
            or not isinstance(opening["moves"], list)
            or not opening["moves"]
            or any(type(move) is not int or not 0 <= move < 361 for move in opening["moves"])
            or opening["id"] in seen_ids
        ):
            raise ValueError("opening allocation is malformed")
        seen_ids.add(opening["id"])
        allocations.append({"attempt": attempt, "id": opening["id"], "moves": list(opening["moves"])})
    return {
        "path": OPENING_SUITE_PATH,
        "file_sha256": _sha256_file(suite_path),
        "checksum": suite["checksum"],
        "allocations": allocations,
        "cycle": False,
    }


def _bound_sources(repo_root: Path, base: str) -> dict:
    sources = {}
    for relative in RUNTIME_SOURCE_PATHS:
        path = repo_root / relative
        if not path.is_file():
            raise ValueError(f"bound runtime source is missing: {relative}")
        current = path.read_bytes()
        try:
            committed = subprocess.run(
                ["git", "show", f"{base}:{relative}"], cwd=repo_root, check=True, capture_output=True
            ).stdout
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"bound runtime source is absent from implementation base: {relative}") from exc
        if current != committed:
            raise ValueError(f"source drift from implementation base: {relative}")
        sources[relative] = hashlib.sha256(current).hexdigest()
    return sources


def build_manifest(repo_root: Path | str, implementation_base_revision: str) -> dict:
    root = Path(repo_root).resolve()
    base = _validate_base_ancestry(root, implementation_base_revision)
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "protocol": PROTOCOL_VERSION,
        "implementation_base_revision": base,
        "matchups": [dict(matchup) for matchup in MATCHUPS],
        "opening_suite": _load_opening_binding(root),
        "runtime_sources": _bound_sources(root, base),
        "versions": {
            "selection": SELECTION_ALGORITHM_VERSION,
            "draw": DRAW_ALGORITHM_VERSION,
            "referee": "b28@200",
            "adjudication": "b28-settled-score-v1",
            "symmetry": {"mode": "katago-default", "requested_symmetry": None},
            "rules": "chinese",
            "komi": "7.5",
            "move_cap": 400,
            "checkpoint_schema": 3,
        },
    }
    manifest["manifest_sha256"] = canonical_digest(manifest, exclude="manifest_sha256")
    return manifest


def create_manifest(output_path: Path | str, repo_root: Path | str, implementation_base_revision: str) -> dict:
    manifest = build_manifest(repo_root, implementation_base_revision)
    encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with Path(output_path).open("x", encoding="utf-8") as output:
        output.write(encoded)
    return manifest


def validate_manifest(manifest: object, repo_root: Path | str) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    if manifest.get("manifest_sha256") != canonical_digest(manifest, exclude="manifest_sha256"):
        raise ValueError("manifest self-digest mismatch")
    expected = build_manifest(repo_root, manifest.get("implementation_base_revision"))
    if manifest != expected:
        source_paths = manifest.get("runtime_sources")
        if isinstance(source_paths, dict) and set(source_paths) == set(RUNTIME_SOURCE_PATHS):
            for relative, expected_digest in source_paths.items():
                if _sha256_file(Path(repo_root) / relative) != expected_digest:
                    raise ValueError(f"source drift: {relative}")
        raise ValueError("manifest does not match the frozen protocol")
    return manifest


def validate_manifest_file(manifest_path: Path | str, repo_root: Path | str) -> dict:
    try:
        manifest = json.loads(Path(manifest_path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load manifest: {exc}") from exc
    return validate_manifest(manifest, repo_root)


def _wilson_interval(wins: int, games: int) -> tuple[float, float]:
    proportion = wins / games
    z2 = _WILSON_Z95 * _WILSON_Z95
    denominator = 1 + z2 / games
    center = (proportion + z2 / (2 * games)) / denominator
    radius = _WILSON_Z95 * math.sqrt((proportion * (1 - proportion) + z2 / (4 * games)) / games) / denominator
    return center - radius, center + radius


def classify_matchup(a_wins: int, *, complete_pairs: int, identity_valid: bool) -> dict:
    if type(complete_pairs) is not int or complete_pairs != 10 or identity_valid is not True:
        return {"classification": "incomplete", "a_wins": a_wins, "complete_pairs": complete_pairs}
    games = complete_pairs * 2
    if type(a_wins) is not int or not 0 <= a_wins <= games:
        return {"classification": "incomplete", "a_wins": a_wins, "complete_pairs": complete_pairs}
    low, high = _wilson_interval(a_wins, games)
    if low > 0.5:
        classification = "persuasive_direction"
    elif high < 0.5:
        classification = "persuasive_inversion"
    elif a_wins > 10:
        classification = "direction_supported"
    elif a_wins == 10:
        classification = "point_tie"
    else:
        classification = "point_inversion"
    return {
        "classification": classification,
        "a_wins": a_wins,
        "complete_pairs": complete_pairs,
        "wilson_ci95": [low, high],
    }


def classify_pilot(results: object) -> dict:
    if not isinstance(results, list) or len(results) != len(MATCHUPS):
        return {"status": "incomplete", "reasons": ["missing_matchup_evidence"]}
    classified = []
    for expected, row in zip(MATCHUPS, results):
        if not isinstance(row, dict) or row.get("matchup_id") != expected["matchup_id"]:
            return {"status": "incomplete", "reasons": ["invalid_evidence_identity"]}
        result = classify_matchup(
            row.get("a_wins"),
            complete_pairs=row.get("complete_pairs"),
            identity_valid=row.get("identity_valid") is True,
        )
        classified.append({"matchup_id": expected["matchup_id"], "profile": expected["profile"], **result})
    if any(row["classification"] == "incomplete" for row in classified):
        return {"status": "incomplete", "reasons": ["incomplete_or_invalid_evidence"], "matchups": classified}

    direction_matchups = sum(row["a_wins"] > 10 for row in classified)
    profile_a_wins = {
        profile: sum(row["a_wins"] for row in classified if row["profile"] == profile)
        for profile in ("rank_1d", "rank_5d", "rank_9d")
    }
    reasons = []
    if any(row["classification"] == "persuasive_inversion" for row in classified):
        reasons.append("persuasive_inversion")
    if direction_matchups < 8:
        reasons.append("fewer_than_8_direction_matchups")
    if any(total <= 30 for total in profile_a_wins.values()):
        reasons.append("profile_aggregate_not_above_30")
    return {
        "status": "fail" if reasons else "pass",
        "reasons": reasons,
        "direction_matchups": direction_matchups,
        "profile_a_wins": profile_a_wins,
        "matchups": classified,
    }
