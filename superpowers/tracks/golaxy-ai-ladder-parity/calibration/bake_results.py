#!/usr/bin/env python3
"""bake_results.py (Task 10, Phase P3b): turn measured per-anchor Elo (vs Golaxy, from
`run_calibration.py`'s `results/summary.json`) into a corrected 40-rung `ladder.py` table.

**Per-band, never global** (per adversarial review): a straight-line correction is fit
SEPARATELY for each of the four strength bands (kyu / amateur-dan / pro / super-pro) --
never one line across all 40 rungs. Adjacent Golaxy levels can plausibly have different
real-Elo-per-rung slopes in the kyu tail vs. the super-pro tail; forcing a single global fit
would misfit one end to make the other look good.

**Ties/reversals are detected and documented, never fabricated away**: `classify_pairs` flags
adjacent anchors whose measured-Elo confidence intervals overlap as indistinguishable ("tie")
and adjacent anchors that are CI-confirmed to have flipped relative to their nominal Golaxy
ordering as "reversed". Neither case is corrected by nudging a config knob until the numbers
look monotonic -- the PRD explicitly expects adjacent Golaxy levels to sometimes be
near-identical in real strength (see `katrain/core/ladder.py`'s module docstring).

This module is pure math (`banded_correction`/`classify_pairs`/`apply_corrections`/
`bump_ladder_version`/`rung_proxy`) plus a thin CLI (`bake`/`main`) -- the pure functions are
unit-tested (`tests/core/test_bake_results.py`, no network, CI-safe); the CLI itself is
operator-run only, exactly like `run_calibration.py`/`run_smoke.py`. It NEVER edits
`katrain/core/ladder.py` directly -- it prints/writes the corrected values for a human to
paste in by hand (README.md's runbook), alongside a bumped `LADDER_VERSION`.

Usage (after a full `run_calibration.py` pass has written `results/summary.json`):
    uv run python \\
        superpowers/tracks/golaxy-ai-ladder-parity/calibration/bake_results.py \\
        --summary superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/summary.json \\
        --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/baked_ladder.json
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# katrain.core.ladder itself is import-light (no Kivy at module scope), but several sibling
# katrain.core modules are not -- katrain.core.base_katrain pulls in Kivy, which parses
# sys.argv on import and would hijack this CLI's own --summary/--out flags. Guard defensively,
# same pattern as run_calibration.py / run_smoke.py, in case a future edit here needs config
# access (e.g. a wide_root_noise-style shipping-config read).
os.environ.setdefault("KIVY_NO_ARGS", "1")

sys.path.insert(0, str(Path(__file__).parent))  # allow `import adapters`-style siblings if ever needed

from katrain.core.ladder import (  # noqa: E402
    LADDER_RUNGS,
    LADDER_VERSION,
    LadderRung,
    config_sanity_key,
    get_rung,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bake_results")

# --- Band classification -------------------------------------------------------------------
# Bands mirror the PRD's coarse strength regimes (kyu / amateur-dan / pro / super-pro).
# Classification uses ONLY the PUBLIC `golaxy_api_level` field (never ladder.py's private
# per-profile tables), so this stays correct even if ladder.py's internal kyu/dan/search
# tables are edited independently. Boundaries mirror ladder.py's own band edges:
# _KYU_PROFILE covers "18级".."1级" (api <=1100); _DAN_PROFILE covers "准1段".."6段"
# (1200<=api<=2300); _SEARCH_VISITS splits "准7段".."9段" (pro, 2400<=api<=3000) from
# "星阵1星".."星阵3星" (super, api>=3100); the api-less rung-40 ceiling is the strongest rung
# of all, so it is classified "super".
BAND_KYU = "kyu"
BAND_AMATEUR = "amateur"
BAND_PRO = "pro"
BAND_SUPER = "super"
BANDS = (BAND_KYU, BAND_AMATEUR, BAND_PRO, BAND_SUPER)

_KYU_MAX_API = 1100
_AMATEUR_MAX_API = 2300
_PRO_MAX_API = 3000


def band_of_rung(rung: LadderRung) -> str:
    """Classify a rung into one of BANDS using ONLY its public `golaxy_api_level` (`None` ->
    the rung-40 ceiling, which is stronger than every named rung -> super)."""
    api = rung.golaxy_api_level
    if api is None:
        return BAND_SUPER
    if api <= _KYU_MAX_API:
        return BAND_KYU
    if api <= _AMATEUR_MAX_API:
        return BAND_AMATEUR
    if api <= _PRO_MAX_API:
        return BAND_PRO
    return BAND_SUPER


# --- banded_correction ------------------------------------------------------------------


def banded_correction(anchors: List[dict]) -> Dict[str, dict]:
    """Per-band offset+slope fit over measured anchor `elo_diff` (measured Elo of OUR engine
    vs. the Golaxy opponent that rung's level claims to match -- i.e. `run_calibration.py`'s
    `elo_vs_opponent`: 0 = perfectly calibrated, +N = our engine measured N Elo STRONGER than
    that Golaxy level (the rung needs weakening), -N = weaker (needs strengthening)).

    Each `anchors` entry: `{"band": str, "rung": int, "elo_diff": float}`. Bands are fit
    INDEPENDENTLY -- a line is fit only across points sharing the same `"band"` key, never
    across all anchors together (a single global fit was rejected by adversarial review: kyu
    and super-pro plausibly have different real-Elo-per-rung slopes). A band with only ONE
    anchor cannot support a slope estimate: it degrades to a flat translate (`slope=0.0`,
    `offset=`that single measured diff) rather than fabricating a trend from one point.

    Returns `{band: {"offset": float, "slope": float, "n": int, "rungs": [int, ...]}}` for
    every band that has >=1 anchor point -- bands absent from `anchors` are simply absent from
    the result; `apply_corrections` leaves rungs in an unmeasured band untouched."""
    by_band: Dict[str, List[dict]] = {}
    for a in anchors:
        by_band.setdefault(a["band"], []).append(a)

    corr: Dict[str, dict] = {}
    for band, points in by_band.items():
        rungs = [float(p["rung"]) for p in points]
        diffs = [float(p["elo_diff"]) for p in points]
        n = len(points)
        if n == 1:
            offset, slope = diffs[0], 0.0
        else:
            mean_r = sum(rungs) / n
            mean_d = sum(diffs) / n
            var_r = sum((r - mean_r) ** 2 for r in rungs)
            if var_r < 1e-9:  # every anchor landed on the same rung number -- no slope signal
                offset, slope = mean_d, 0.0
            else:
                cov = sum((r - mean_r) * (d - mean_d) for r, d in zip(rungs, diffs))
                slope = cov / var_r
                offset = mean_d - slope * mean_r
        corr[band] = {"offset": offset, "slope": slope, "n": n, "rungs": sorted(int(p["rung"]) for p in points)}
    return corr


# --- classify_pairs ----------------------------------------------------------------------


def classify_pairs(measured_elos_with_ci: List[dict]) -> Dict[Tuple[int, int], str]:
    """Adjacent-pair status from measured Elo+95%CI, in the given (weak->strong) list order.
    Each entry: `{"rung": int, "elo": float, "lo": float, "hi": float}`.

    - Overlapping CI (the two Elo-with-error-bar intervals intersect) -> `"tie"`: the two
      rungs are statistically indistinguishable at this sample size. Never nudge a config knob
      to force them apart -- record the tie (PRD: adjacent Golaxy levels can genuinely be
      near-identical in real strength).
    - Non-overlapping AND the later (nominally-stronger) rung measured LOWER -> `"reversed"`:
      a real, CI-confirmed strength inversion between adjacent Golaxy labels.
    - Non-overlapping AND the later rung measured higher -> `"ok"`: consistent with the
      nominal ordering.

    Returns `{(rung_i, rung_{i+1}): status, ...}` for each adjacent pair in the input list
    (in list order -- callers must pass anchors already ordered weak->strong)."""
    status: Dict[Tuple[int, int], str] = {}
    for i in range(len(measured_elos_with_ci) - 1):
        a, b = measured_elos_with_ci[i], measured_elos_with_ci[i + 1]
        overlap = a["lo"] <= b["hi"] and b["lo"] <= a["hi"]
        if overlap:
            state = "tie"
        elif b["elo"] < a["elo"]:
            state = "reversed"
        else:
            state = "ok"
        status[(a["rung"], b["rung"])] = state
    return status


# --- rung_proxy --------------------------------------------------------------------------


def rung_proxy(rung: LadderRung) -> float:
    """Numeric strength-ORDERING proxy for a (possibly baked) rung config -- a thin alias for
    `katrain.core.ladder.config_sanity_key`, re-exported here so bake_results' own tests/CLI
    have one import path. Per `config_sanity_key`'s own docstring: this is a CONFIG sanity
    ordering (ties expected for same-profile/same-visits rungs), NOT a measured-Elo value --
    `apply_corrections` uses it only to verify baked configs still satisfy the non-decreasing
    invariant, never to claim a strength number."""
    return config_sanity_key(rung)


# --- apply_corrections ---------------------------------------------------------------------
# Provisional Elo<->knob conversion constants. These translate a band's measured Elo offset
# into a shift of that band's actual calibration knob (humanSL profile step for kyu/amateur,
# maxVisits for pro/super). Both are best-effort placeholders pending a REAL measured
# Elo-per-step curve from P3b's own anchors -- refine them once enough same-band anchors exist
# to fit one directly, instead of assuming it.
_ELO_PER_KYU_STEP = 100.0  # matches ladder.py's own ~100-Elo spacing between adjacent named
# kyu/dan rungs (see _GOLAXY_WEAK_TO_STRONG's display_elo deltas).
_ELO_PER_VISIT_DOUBLING = 50.0  # rule-of-thumb Elo gain per visits-doubling for a fixed net.

_KYU_STEPS: Tuple[str, ...] = tuple(f"rank_{k}k" for k in range(20, 0, -1))  # rank_20k (weakest) .. rank_1k
_DAN_STEPS: Tuple[str, ...] = tuple(f"rank_{d}d" for d in range(1, 10))  # rank_1d .. rank_9d (headroom above 6d)


def _band_table(band: str) -> Optional[Tuple[str, ...]]:
    if band == BAND_KYU:
        return _KYU_STEPS
    if band == BAND_AMATEUR:
        return _DAN_STEPS
    return None  # pro/super are pure-visits bands: no profile table


def _shift_profile(profile: Optional[str], steps: int, table: Tuple[str, ...]) -> Optional[str]:
    """Move `profile` `steps` positions up (positive=stronger) within `table`, clamped to its
    bounds. A profile not found in `table` (band/table mismatch, or `None`) is returned
    UNCHANGED -- guessing a replacement for an unrecognized name would be worse than a no-op."""
    if profile is None or profile not in table:
        return profile
    idx = table.index(profile)
    new_idx = max(0, min(len(table) - 1, idx + steps))
    return table[new_idx]


def _shift_visits(visits: int, delta_elo: float) -> int:
    """Scale `visits` by `2**(delta_elo / _ELO_PER_VISIT_DOUBLING)`, rounded, floor 1."""
    factor = 2.0 ** (delta_elo / _ELO_PER_VISIT_DOUBLING)
    return max(1, round(visits * factor))


def apply_corrections(rungs: List[LadderRung], corr: Dict[str, dict]) -> List[LadderRung]:
    """Apply each band's `{offset,slope}` to every rung in that band, moving its calibration
    knob (humanSL profile for kyu/amateur, `maxVisits` for pro/super) toward the corrected
    target `delta = offset + slope * rung.rung`. Bands ABSENT from `corr` (not yet measured)
    are left completely UNCHANGED -- this function never extrapolates a correction for a band
    it has no anchor data for.

    Returns NEW `LadderRung` instances (`dataclasses.replace` -- the dataclass is frozen);
    `rungs` itself is never mutated. A final pass (`_clamp_non_decreasing`) re-clamps any
    adjacent pair whose `config_sanity_key` a bake-induced shift would regress, back up to a
    tie with its predecessor: per the PRD, ties are expected/fine, but a REGRESSION is a
    config bug introduced by baking, not a measured-Elo finding, and must never survive
    silently."""
    out: List[LadderRung] = []
    for r in rungs:
        band = band_of_rung(r)
        c = corr.get(band)
        if c is None:
            out.append(r)
            continue
        delta = c["offset"] + c["slope"] * r.rung
        table = _band_table(band)
        if table is not None and r.human_sl_profile is not None:
            steps = round(delta / _ELO_PER_KYU_STEP)
            out.append(replace(r, human_sl_profile=_shift_profile(r.human_sl_profile, steps, table)))
        else:
            out.append(replace(r, max_visits=_shift_visits(r.max_visits, delta)))
    return _clamp_non_decreasing(out)


_MAX_VISITS_CEILING = 100_000  # defensive backstop against a pathological correction blowing
# visits up unboundedly; a real bake's Elo deltas should stay far below what would ever
# approach this (see the constants' docstring above).


def _bump_until(r: LadderRung, target_key: float) -> Tuple[LadderRung, float]:
    """Bump ONLY `r`'s own knob (profile step up / visits up) until `config_sanity_key(r)`
    reaches `target_key`, or the knob's range is exhausted. Never touches any other rung.

    Search-mechanism visits are solved for DIRECTLY: `config_sanity_key` is a closed form
    (`540 + 100*log2(visits)`) for every search rung regardless of pro/super band, so we
    invert it instead of nudging iteratively (a huge target delta would otherwise need
    thousands of small steps). HumanSL profiles are scanned directly (the table has <=29
    entries, so an exhaustive scan is cheap and exact)."""
    band = band_of_rung(r)
    table = _band_table(band)
    if table is not None and r.human_sl_profile is not None and r.human_sl_profile in table:
        idx = table.index(r.human_sl_profile)
        for j in range(idx, len(table)):
            candidate = replace(r, human_sl_profile=table[j])
            if config_sanity_key(candidate) >= target_key - 1e-9:
                return candidate, config_sanity_key(candidate)
        candidate = replace(r, human_sl_profile=table[-1])  # exhausted: strongest profile available
        return candidate, config_sanity_key(candidate)

    needed = math.ceil(2.0 ** ((target_key - 540.0) / 100.0))
    candidate = replace(r, max_visits=max(r.max_visits, min(_MAX_VISITS_CEILING, needed)))
    key = config_sanity_key(candidate)
    while key < target_key - 1e-9 and candidate.max_visits < _MAX_VISITS_CEILING:
        candidate = replace(candidate, max_visits=candidate.max_visits + 1)
        key = config_sanity_key(candidate)
    return candidate, key


def _clamp_non_decreasing(rungs: List[LadderRung]) -> List[LadderRung]:
    """Walk weak->strong; whenever a rung's `config_sanity_key` regressed below its
    predecessor's (a bake-induced ordering flip), bump ONLY that rung's own knob until it ties
    (>=) the predecessor -- never touch the predecessor, and never force an EXACT tie when a
    bump naturally lands above it (extra distinction is fine; forced sameness is not the
    goal). Bounded retries guard an unreachable target (already at a knob's ceiling); in that
    rare case the best-attainable rung is kept and a warning logged, since an unresolvable
    regression is a signal for a human to re-examine the anchors, not something to hide."""
    out: List[LadderRung] = []
    prev_key: Optional[float] = None
    for r in rungs:
        key = config_sanity_key(r)
        if prev_key is not None and key < prev_key - 1e-9:
            r, key = _bump_until(r, prev_key)
            if key < prev_key - 1e-9:
                log.warning(
                    "rung %d: could not fully clamp to non-decreasing config_sanity_key "
                    "(%.3f < predecessor %.3f) -- knob range exhausted; flag for operator review",
                    r.rung,
                    key,
                    prev_key,
                )
        out.append(r)
        prev_key = key
    return out


# --- LADDER_VERSION bump ------------------------------------------------------------------


def bump_ladder_version(current: str = LADDER_VERSION) -> str:
    """`'v3' -> 'v4'` (also accepts a bare digit string `'3' -> '4'`, matching whichever
    convention `ladder.py`'s `LADDER_VERSION` currently uses). The bake CLI always prints the
    NEW version alongside the new table values so an operator pastes both together -- an
    unbumped version after a real bake would look identical to the pre-bake provisional table
    to any future reader."""
    m = re.fullmatch(r"(v)?(\d+)", current.strip())
    if not m:
        raise ValueError(f"unrecognized LADDER_VERSION format: {current!r} (expected 'vN' or 'N')")
    prefix, n = m.group(1) or "", int(m.group(2))
    return f"{prefix}{n + 1}"


# --- Full bake pipeline (operator CLI) ------------------------------------------------------


def _measured_from_summary(summary: dict) -> List[dict]:
    """`[{'rung':int,'elo':float,'lo':float,'hi':float}, ...]` sorted weak->strong, from
    `run_calibration.py`'s `summary.json` `"anchors"` list (each entry has `elo_vs_opponent` +
    `elo_ci95`)."""
    out = []
    for a in summary.get("anchors", []):
        lo, hi = a["elo_ci95"]
        out.append({"rung": a["rung"], "elo": a["elo_vs_opponent"], "lo": lo, "hi": hi})
    out.sort(key=lambda a: a["rung"])
    return out


def _anchors_for_banded_correction(measured: List[dict]) -> List[dict]:
    return [{"band": band_of_rung(get_rung(m["rung"])), "rung": m["rung"], "elo_diff": m["elo"]} for m in measured]


def bake(summary: dict) -> dict:
    """Full bake pipeline: measured anchors -> per-band correction -> adjacent-anchor
    tie/reversal classification -> corrected 40-rung table -> re-verified non-decreasing
    `config_sanity_key`. Returns a plain JSON-serializable dict; NEVER mutates
    `katrain.core.ladder.LADDER_RUNGS` or writes to `ladder.py` -- the operator pastes the
    result in by hand (see README.md)."""
    measured = _measured_from_summary(summary)
    if not measured:
        raise ValueError("summary has no 'anchors' -- nothing to bake")

    anchors = _anchors_for_banded_correction(measured)
    corr = banded_correction(anchors)
    pair_status = classify_pairs(measured)
    new_rungs = apply_corrections(LADDER_RUNGS, corr)

    keys = [rung_proxy(r) for r in new_rungs]
    regressions = [
        f"{new_rungs[i - 1].rung}-{new_rungs[i].rung}" for i in range(1, len(keys)) if keys[i] < keys[i - 1] - 1e-9
    ]

    return {
        "ladder_version": bump_ladder_version(LADDER_VERSION),
        "banded_correction": corr,
        "adjacent_anchor_status": {f"{a}-{b}": s for (a, b), s in pair_status.items()},
        "documented_ties": [f"{a}-{b}" for (a, b), s in pair_status.items() if s == "tie"],
        "documented_reversals": [f"{a}-{b}" for (a, b), s in pair_status.items() if s == "reversed"],
        # Should always be [] -- _clamp_non_decreasing guarantees it except at an exhausted
        # knob ceiling (logged as a warning there); surfaced again here for the CLI printout.
        "config_sanity_regressions_after_clamp": regressions,
        "rungs": [
            {
                "rung": r.rung,
                "golaxy_level_name": r.golaxy_level_name,
                "mechanism": r.mechanism,
                "human_sl_profile": r.human_sl_profile,
                "max_visits": r.max_visits,
                "root_policy_temperature": r.root_policy_temperature,
            }
            for r in new_rungs
        ],
    }


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--summary",
        default=str(Path(__file__).parent / "results" / "summary.json"),
        help="run_calibration.py's summary.json (per-anchor elo_vs_opponent + elo_ci95)",
    )
    p.add_argument(
        "--out",
        default=str(Path(__file__).parent / "results" / "baked_ladder.json"),
        help="where to write the full baked-table JSON (for the operator to transcribe into ladder.py)",
    )
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
    summary_path = Path(args.summary)
    if not summary_path.is_file():
        raise SystemExit(f"no summary at {summary_path} -- run run_calibration.py first")
    summary = json.loads(summary_path.read_text())
    result = bake(summary)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    log.info("=== bake result (LADDER_VERSION %s -> %s) ===", LADDER_VERSION, result["ladder_version"])
    for band, c in result["banded_correction"].items():
        log.info(
            "  band %-8s offset=%+8.2f slope=%+7.4f  n=%d anchors=%s", band, c["offset"], c["slope"], c["n"], c["rungs"]
        )
    if result["documented_ties"]:
        log.info("  documented ties (overlapping CI, NOT fake-distinguished): %s", result["documented_ties"])
    if result["documented_reversals"]:
        log.warning("  documented REVERSALS (CI-confirmed strength inversion): %s", result["documented_reversals"])
    if result["config_sanity_regressions_after_clamp"]:
        log.error(
            "  UNRESOLVED config-sanity regressions after clamping: %s -- investigate before shipping",
            result["config_sanity_regressions_after_clamp"],
        )
    else:
        log.info("  config_sanity_key non-decreasing across all 40 baked rungs: OK")
    log.info(
        "wrote full baked table to %s -- paste the relevant values into katrain/core/ladder.py "
        "(and bump LADDER_VERSION to %s) BY HAND; this tool never edits ladder.py directly.",
        out_path,
        result["ladder_version"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
