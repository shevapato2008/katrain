#!/usr/bin/env python3
"""Generate or verify the frozen exp3 HumanSL boundary opening allocation."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path


CALIBRATION_DIR = Path(__file__).resolve().parent
PRIOR_SUITE_PATH = CALIBRATION_DIR / "opening_suite_v1.json"
SUITE_PATH = CALIBRATION_DIR / "opening_suite_boundary_v1.json"
ALLOCATION_PATH = CALIBRATION_DIR / "opening_allocation_boundary_v1.json"
KNOWN_ENDPOINTS_PATH = CALIBRATION_DIR / "known_endpoints_exp3_v1.json"
SEED = 20260722
TRANSITIONS = (
    "rank_5d__rank_6d",
    "rank_6d__rank_7d",
    "rank_7d__rank_8d",
    "rank_8d__rank_9d",
)
PHASES = (("screen", (2, 5, 10, 20, 30), 20), ("confirm", (2, 5, 10, 20, 30, 40), 40))


def canonical_digest(payload: dict, digest_field: str) -> str:
    canonical = {key: value for key, value in payload.items() if key != digest_field}
    data = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def generate() -> tuple[dict, dict]:
    prior = json.loads(PRIOR_SUITE_PATH.read_text())
    seen = {tuple(opening["moves"]) for opening in prior["openings"]}
    rng = random.Random(SEED)
    openings = []
    allocations = {}
    next_id = 1
    for phase, visits_grid, attempts in PHASES:
        for transition in TRANSITIONS:
            for visits in visits_grid:
                ids = []
                for _attempt in range(attempts):
                    while True:
                        moves = tuple(rng.sample(range(19 * 19), 8))
                        if moves not in seen:
                            break
                    seen.add(moves)
                    opening_id = f"b{next_id:04d}"
                    next_id += 1
                    openings.append({"id": opening_id, "moves": list(moves)})
                    ids.append(opening_id)
                allocations[f"{phase}:{transition}:{visits}"] = ids
    suite = {
        "board_size": 19,
        "generation": (
            "Python random.Random(20260722); repeatedly sample eight distinct intersections from range(361), "
            "rejecting sequences already generated or present in humansl-opening-suite-v1."
        ),
        "opening_count": len(openings),
        "openings": openings,
        "seed": SEED,
        "suite_id": "humansl-boundary-opening-suite-v1",
    }
    suite["checksum"] = canonical_digest(suite, "checksum")
    allocation = {
        "allocation_id": "humansl-boundary-opening-allocation-v1",
        "allocations": allocations,
        "confirmation_attempt_cap": 40,
        "confirmation_visits": [2, 5, 10, 20, 30, 40],
        "protocol_version": "exp3-boundary-v1",
        "screening_attempt_cap": 20,
        "screening_visits": [2, 5, 10, 20, 30],
        "suite_checksum": suite["checksum"],
        "suite_id": suite["suite_id"],
        "transitions": list(TRANSITIONS),
    }
    allocation["digest"] = canonical_digest(allocation, "digest")
    return suite, allocation


def check() -> None:
    suite, allocation = generate()
    if not SUITE_PATH.is_file() or SUITE_PATH.read_bytes() != canonical_bytes(suite):
        raise ValueError(f"generated boundary suite differs from {SUITE_PATH}")
    if not ALLOCATION_PATH.is_file() or ALLOCATION_PATH.read_bytes() != canonical_bytes(allocation):
        raise ValueError(f"generated boundary allocation differs from {ALLOCATION_PATH}")
    sys.path.insert(0, str(CALIBRATION_DIR))
    import run_selfplay

    run_selfplay.load_boundary_opening_allocation(SUITE_PATH, ALLOCATION_PATH)
    known, _digest = run_selfplay.load_known_endpoints(KNOWN_ENDPOINTS_PATH)
    if KNOWN_ENDPOINTS_PATH.read_bytes() != canonical_bytes(known):
        raise ValueError(f"known endpoints manifest is not canonical JSON: {KNOWN_ENDPOINTS_PATH}")
    print("1360 allocations verified")


def write(paths: list[Path]) -> None:
    suite_path, allocation_path = paths
    if suite_path.exists() or allocation_path.exists():
        raise FileExistsError("safe write refuses to replace an existing boundary asset")
    suite, allocation = generate()
    with suite_path.open("xb") as destination:
        destination.write(canonical_bytes(suite))
    try:
        with allocation_path.open("xb") as destination:
            destination.write(canonical_bytes(allocation))
    except BaseException:
        suite_path.unlink()
        raise
    print(f"wrote {len(suite['openings'])} globally unique openings")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--write", nargs=2, type=Path, metavar=("SUITE", "ALLOCATION"))
    args = parser.parse_args()
    if args.check:
        check()
    else:
        write(args.write)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
