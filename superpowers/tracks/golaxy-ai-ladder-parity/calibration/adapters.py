"""Calibration adapters: shared ladder query + typed Golaxy opponent + black-relative
scoring. Injected httpx.AsyncClient (MockTransport in tests). Imports katrain.*; nothing
imports this. Golaxy wire uses ladder.colrow_to_golaxy (gold-standard tested), NOT
web/platforms/golaxy/coords (top-anchored -> mirror)."""

from __future__ import annotations

import math
from typing import List, Optional, Tuple, Union

import httpx

from katrain.core.engine import BaseEngine  # for get_rules: send the SAME normalized rules as runtime
from katrain.core.ladder import (
    LadderRung,
    rung_engine_params,
    ladder_override_settings,
    pick_ladder_move,
    colrow_to_gtp,
    colrow_to_golaxy,
    golaxy_to_colrow,
    LadderMoveError,
)
from katrain.web.platforms.golaxy.engine_client import engine_genmove, GOLAXY_AI_LEVELS

_VALID_WIRE = {row["elo_score"] for row in GOLAXY_AI_LEVELS}  # only real api levels; excludes display_elo


def _assert_real_wire_level(level: int) -> None:
    if level not in _VALID_WIRE:
        raise ValueError(
            f"refusing to send non-wire level {level!r} (not a GOLAXY_AI_LEVELS elo_score; never send display_elo)"
        )


def _golaxy_history_to_gtp(moves_golaxy: List[int], bs: int) -> list:
    out = []
    for i, c in enumerate(moves_golaxy):
        dec = golaxy_to_colrow(c, bs)
        player = "B" if i % 2 == 0 else "W"
        out.append([player, colrow_to_gtp(dec[0], dec[1]) if dec != "unknown" else "pass"])
    return out


def build_ladder_analysis_query(moves_golaxy, rung: LadderRung, board_size, komi, rules, wide_root_noise) -> dict:
    """Shared strength-relevant query (contract-tested vs the REAL runtime builder). `rules`
    is a ruleset NAME (e.g. 'chinese'); it is normalized via the SAME BaseEngine.get_rules the
    runtime uses, so the emitted `rules` value is byte-identical. No maxTime (pure visits)."""
    ov = dict(ladder_override_settings(rung))
    ov["wideRootNoise"] = wide_root_noise
    moves = _golaxy_history_to_gtp(moves_golaxy, board_size)
    return {
        "rules": BaseEngine.get_rules(rules),
        "komi": komi,
        "boardXSize": board_size,
        "boardYSize": board_size,
        "moves": moves,
        "analyzeTurns": [len(moves)],
        "maxVisits": rung_engine_params(rung)["visits"],
        "includePolicy": True,
        "includeOwnership": False,
        "overrideSettings": ov,
    }


async def our_move(
    client,
    base_url,
    moves_golaxy,
    rung: LadderRung,
    board_size=19,
    komi=7.5,
    rules="chinese",
    wide_root_noise=0.04,
) -> Union[int, str]:
    q = build_ladder_analysis_query(moves_golaxy, rung, board_size, komi, rules, wide_root_noise)
    r = await client.post(f"{base_url}/analyze", json=q, timeout=httpx.Timeout(180.0, connect=10.0))
    r.raise_for_status()
    try:
        picked = pick_ladder_move(r.json(), (board_size, board_size), rung.mechanism)
    except LadderMoveError:
        return "unavailable"  # certified move not derivable -> harness marks the game inconclusive_engine
    if picked == "pass":
        return "pass"
    return colrow_to_golaxy(picked[0], picked[1], board_size)


def load_engine_wide_root_noise(engine_config: dict) -> float:
    """Read wideRootNoise from the SAME shipping engine config the runtime uses (config.json's
    `engine.wide_root_noise`). run_calibration passes this into our_move — never the hard-coded
    default — so calibration and production can never use different values (G2)."""
    return float(engine_config["wide_root_noise"])


def _valid_sentinels(pass_code, resign_code, board_size):
    """Return (pass_code, resign_code) keeping only values that are plain ints, OUT of the board
    range [0, bs*bs), and DISTINCT from each other. Anything else -> None (so it can never turn an
    ordinary reply into a scored resign/pass). Guards R5-H2: equal or in-board codes are rejected."""
    n = board_size * board_size

    def ok(c):
        return type(c) is int and not (0 <= c < n)

    p = pass_code if ok(pass_code) else None
    r = resign_code if ok(resign_code) else None
    if p is not None and r is not None and p == r:  # ambiguous -> trust neither
        return (None, None)
    return (p, r)


async def golaxy_move(
    client,
    moves_golaxy,
    rung: LadderRung,
    token,
    board_size=19,
    komi=7.5,
    rule="chinese",
    pass_code=None,
    resign_code=None,
) -> Union[int, str]:
    """Classify Golaxy's reply. A board coord -> int. A coord matching a SMOKE-VERIFIED, VALIDATED
    (out-of-board, distinct) resign/pass code -> 'resign'/'pass'. Any OTHER out-of-board value ->
    'terminal' (UNVERIFIED/malformed) — the harness never scores those (H1). Codes are None until
    smoke captures them (Task 9); invalid codes are dropped by _valid_sentinels, so pre-smoke (and
    on any misconfig) every stop is 'terminal' (safe). resign is checked before pass."""
    level = rung.golaxy_api_level
    _assert_real_wire_level(level)  # display_elo structurally unreachable
    pass_code, resign_code = _valid_sentinels(pass_code, resign_code, board_size)
    res = await engine_genmove(
        client, moves=moves_golaxy, level=level, access_token=token, komi=komi, rule=rule, board_size=board_size
    )
    if resign_code is not None and res.coord == resign_code:
        return "resign"
    if pass_code is not None and res.coord == pass_code:
        return "pass"
    if golaxy_to_colrow(res.coord, board_size) == "unknown":
        return "terminal"  # unverified out-of-board -> inconclusive upstream
    return res.coord


async def adjudicate(
    client, base_url, moves_golaxy, board_size=19, komi=7.5, rules="chinese", visits=200
) -> Tuple[Optional[float], bool]:
    """Black-relative final score via reportAnalysisWinratesAs=BLACK. Missing/non-finite ->
    (None, False). `settled` requires a low-uncertainty endgame (see criteria)."""
    q = {
        "rules": BaseEngine.get_rules(rules),
        "komi": komi,
        "boardXSize": board_size,
        "boardYSize": board_size,
        "moves": _golaxy_history_to_gtp(moves_golaxy, board_size),
        "analyzeTurns": [len(moves_golaxy)],
        "maxVisits": visits,
        "includeOwnership": True,
        "includePolicy": False,
        "overrideSettings": {"reportAnalysisWinratesAs": "BLACK"},
    }
    r = await client.post(f"{base_url}/analyze", json=q, timeout=httpx.Timeout(180.0, connect=10.0))
    r.raise_for_status()
    a = r.json()
    root = a.get("rootInfo") or {}
    lead = root.get("scoreLead")
    if lead is None or not isinstance(lead, (int, float)) or not math.isfinite(lead):
        return (None, False)
    return (float(lead), _is_settled(a, board_size, lead))


def _is_settled(analysis: dict, board_size: int, lead: float) -> bool:
    """Conservative endgame check (G5). Requires: (1) ownership array present with EXACTLY
    board_size**2 finite entries; (2) >=98% of points decisively owned (|own|>0.9); (3) the
    undecided margin cannot flip the winner — the count of undecided points (which could each
    swing ~2 pts) is comfortably smaller than the current lead. Anything else -> NOT settled
    (caller records inconclusive_unsettled). A separate score-stability re-check (re-analyze
    at higher visits, assert |Δ scoreLead| < 1.0) is applied by run_calibration before trusting
    a move-cap game; two-natural-pass games are inherently more trustworthy."""
    own = analysis.get("ownership")
    n = board_size * board_size
    if (
        not isinstance(own, list)
        or len(own) != n
        or not all(isinstance(o, (int, float)) and math.isfinite(o) for o in own)
    ):
        return False
    undecided = sum(1 for o in own if abs(o) <= 0.9)
    if undecided / n > 0.02:  # <98% decisive -> live fight/dame remains
        return False
    # undecided points could each swing ~2 points; require the lead to dominate that swing.
    if abs(lead) <= 2.0 * undecided + 1.0:
        return False
    return True
