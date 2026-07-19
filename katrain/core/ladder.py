"""Golaxy-parity strength ladder: 40 rungs of local-KataGo config + pure helpers
shared by LadderStrategy (runtime) and the calibration harness.

VALUES ARE PROVISIONAL (offline, PRD §6/§7); empirical calibration (P3b) overwrites
them. `config_sanity_key` is a config sanity check ONLY — ties between adjacent
same-profile rungs are EXPECTED and fine (PRD §2: adjacent Golaxy levels can have
near-identical real strength). True monotonicity comes from measured games, not
this key."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

MECHANISMS = ("humansl", "humansl_search", "net_search")
_COLS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"  # GTP columns, 'I' skipped

# Bumped by calibration/bake_results.py's bump_ladder_version() every time a REAL measured-Elo
# bake overwrites the table below (Phase P3b, Task 10). "v1" = the current PROVISIONAL table
# (offline PRD reasoning only, never yet measured against live Golaxy) -- see the module
# docstring above.
LADDER_VERSION = "v1"


class LadderMoveError(Exception):
    """A rung's required analysis output is absent/malformed, so no certified move can be
    selected. Callers MUST NOT substitute an uncalibrated move: LadderStrategy converts this
    to LadderUnavailable (no move); the calibration harness converts it to an inconclusive game."""


@dataclass(frozen=True)
class LadderRung:
    rung: int
    golaxy_level_name: Optional[str]
    golaxy_api_level: Optional[int]  # eloScore = the `level` wire param (calibration only)
    display_elo: Optional[int]
    ref_rank: str
    net: str  # v1: always 'b18' (== shipping engine)
    mechanism: str
    human_sl_profile: Optional[str]
    max_visits: int
    human_sl_params: Dict = field(default_factory=dict)
    backend_hint: str = "server"
    root_policy_temperature: float = 1.0


_GOLAXY_WEAK_TO_STRONG = [
    ("18级", 220, -600, "业余18级"),
    ("17级", 230, -500, "业余17级"),
    ("16级", 240, -400, "业余16级"),
    ("15级", 250, -300, "业余15级"),
    ("14级", 260, -200, "业余14级"),
    ("13级", 270, -100, "业余13级"),
    ("12级", 280, 0, "业余12级"),
    ("11级", 290, 100, "业余11级"),
    ("10级", 300, 200, "业余10级"),
    ("9级", 380, 300, "业余9级"),
    ("8级", 460, 400, "业余8级"),
    ("7级", 540, 500, "业余7级"),
    ("6级", 620, 600, "业余6级"),
    ("5级", 700, 700, "业余5级"),
    ("4级", 800, 800, "业余4级"),
    ("3级", 900, 900, "业余3级"),
    ("2级", 1000, 1000, "业余2级"),
    ("1级", 1100, 1100, "业余1级"),
    ("准1段", 1200, 1200, "业余准1段"),
    ("1段", 1300, 1300, "业余1段"),
    ("准2段", 1400, 1400, "业余准2段"),
    ("2段", 1500, 1500, "业余2段"),
    ("准3段", 1600, 1600, "业余准3段"),
    ("3段", 1700, 1700, "业余3段"),
    ("准4段", 1800, 1800, "业余准4段"),
    ("4段", 1900, 1900, "业余4段"),
    ("准5段", 2000, 2000, "业余准5段"),
    ("5段", 2100, 2100, "业余5段"),
    ("准6段", 2200, 2200, "业余准6段"),
    ("6段", 2300, 2300, "业余6段"),
    ("准7段", 2400, 2400, "野狐9D"),
    ("7段", 2500, 2500, "野狐9D"),
    ("准8段", 2600, 2600, "野狐9D"),
    ("8段", 2800, 2800, "野狐9D"),
    ("准9段", 2900, 2900, "野狐9D"),
    ("9段", 3000, 3100, "野狐9D"),
    ("星阵1星", 3100, 3400, "职业/野狐9D+"),
    ("星阵2星", 3200, 3700, "职业/野狐9D+"),
    ("星阵3星", 3300, 4000, "职业/野狐9D+"),
]

# Provisional humanSL profile per Golaxy level (kyu/amateur-dan bands, visits=1). Adjacent
# levels MAY share a profile (expected ties). PRD §7 anchors interpolated.
_KYU_PROFILE = {
    "18级": "rank_20k",
    "17级": "rank_19k",
    "16级": "rank_18k",
    "15级": "rank_17k",
    "14级": "rank_16k",
    "13级": "rank_15k",
    "12级": "rank_14k",
    "11级": "rank_13k",
    "10级": "rank_12k",
    "9级": "rank_11k",
    "8级": "rank_10k",
    "7级": "rank_9k",
    "6级": "rank_8k",
    "5级": "rank_7k",
    "4级": "rank_6k",
    "3级": "rank_5k",
    "2级": "rank_4k",
    "1级": "rank_3k",
}
_DAN_PROFILE = {
    "准1段": "rank_1d",
    "1段": "rank_1d",
    "准2段": "rank_2d",
    "2段": "rank_2d",
    "准3段": "rank_3d",
    "3段": "rank_3d",
    "准4段": "rank_4d",
    "4段": "rank_4d",
    "准5段": "rank_5d",
    "5段": "rank_5d",
    "准6段": "rank_6d",
    "6段": "rank_6d",
}
# High amateur / pro / super-pro: pure b18 search, increasing visits (strength-first).
_SEARCH_VISITS = {
    "准7段": 8,
    "7段": 12,
    "准8段": 20,
    "8段": 40,
    "准9段": 80,
    "9段": 140,
    "星阵1星": 220,
    "星阵2星": 350,
    "星阵3星": 480,
}


def _band(name: str):
    if name in _KYU_PROFILE:
        temp = 1.1 if name in ("18级", "17级", "16级", "15级") else 1.0
        return ("humansl", _KYU_PROFILE[name], 1, {}, temp)
    if name in _DAN_PROFILE:
        return ("humansl", _DAN_PROFILE[name], 1, {}, 1.0)
    return ("net_search", None, _SEARCH_VISITS[name], {}, 1.0)


def _build_ladder() -> List[LadderRung]:
    rungs = []
    for i, (name, api, disp, ref) in enumerate(_GOLAXY_WEAK_TO_STRONG):
        mech, prof, visits, params, temp = _band(name)
        rungs.append(LadderRung(i + 1, name, api, disp, ref, "b18", mech, prof, visits, dict(params), "server", temp))
    # Rung 40: ceiling. v1 = b18@500 on the session engine (honest net='b18'). A true
    # b28@:8002 ceiling is a documented follow-up (calibration/README.md), NOT exposed as net.
    rungs.append(LadderRung(40, None, None, None, "最强", "b18", "net_search", None, 500, {}, "server", 1.0))
    return rungs


LADDER_RUNGS: List[LadderRung] = _build_ladder()
_BY_RUNG = {r.rung: r for r in LADDER_RUNGS}


def get_rung(n: int) -> LadderRung:
    if n not in _BY_RUNG:
        raise ValueError(f"rung out of range 1..40: {n!r}")
    return _BY_RUNG[n]


def ladder_override_settings(rung: LadderRung) -> Dict:
    """overrideSettings for a rung. Forces reportAnalysisWinratesAs=BLACK (matches the
    runtime engine + makes score/winrate black-relative for calibration scoring)."""
    ov: Dict = {"reportAnalysisWinratesAs": "BLACK"}
    if rung.human_sl_profile:
        ov["humanSLProfile"] = rung.human_sl_profile
        ov["ignorePreRootHistory"] = False
    if abs(rung.root_policy_temperature - 1.0) > 1e-9:
        ov["rootPolicyTemperature"] = rung.root_policy_temperature
    ov.update(rung.human_sl_params or {})
    return ov


def rung_engine_params(rung: LadderRung) -> Dict:
    """{'visits','extra_settings'}. visits -> top-level maxVisits; extra_settings ->
    overrideSettings. maxVisits is NEVER in extra_settings."""
    return {"visits": rung.max_visits, "extra_settings": ladder_override_settings(rung)}


def colrow_to_gtp(col: int, row0: int) -> str:
    return f"{_COLS[col]}{row0 + 1}"


def gtp_to_colrow(gtp: str, board_size: Tuple[int, int]) -> Union[Tuple[int, int], str]:
    g = gtp.strip().lower()
    if g in ("pass", "", "tt"):
        return "pass"
    return (_COLS.index(gtp[0].upper()), int(gtp[1:]) - 1)


def colrow_to_golaxy(col: int, row0: int, bs: int = 19) -> int:
    """KaTrain-core (col,row0 bottom-origin) -> Golaxy wire int. Gold-standard tested."""
    if not (0 <= col < bs and 0 <= row0 < bs):
        raise ValueError(f"colrow out of range for bs={bs}: ({col},{row0})")
    return (bs - 1 - row0) * bs + col


def golaxy_to_colrow(coord: int, bs: int = 19) -> Union[Tuple[int, int], str]:
    if not (0 <= coord < bs * bs):
        return "unknown"  # out-of-board wire value; caller treats as inconclusive terminal
    return (coord % bs, bs - 1 - coord // bs)


def _weighted_policy_pick(human_policy, board_size):
    from katrain.core.ai import weighted_selection_without_replacement

    bx, by = board_size
    moves = []
    for x in range(bx):
        for y in range(by):
            idx = (by - y - 1) * bx + x
            if idx < len(human_policy) and human_policy[idx] > 0:
                moves.append(((x, y), human_policy[idx]))
    if len(human_policy) > bx * by and human_policy[-1] > 0:
        moves.append(("pass", human_policy[-1]))
    if not moves:
        return "pass"
    return weighted_selection_without_replacement(moves, 1)[0][0]


def _valid_policy(hp, expected_len) -> bool:
    return (
        isinstance(hp, list)
        and len(hp) == expected_len
        and all(isinstance(v, (int, float)) and math.isfinite(v) for v in hp)
        and sum(v for v in hp if v > 0) > 0
    )


def _is_plain_int(x) -> bool:
    return type(x) is int  # excludes bool (a subclass of int) and float


def _validate_gtp_on_board(mv, board_size):
    """Parse a GTP move and bounds-check it, or raise LadderMoveError."""
    try:
        cr = gtp_to_colrow(mv, board_size)
    except (ValueError, IndexError, KeyError) as e:
        raise LadderMoveError(f"search mechanism: unparseable move {mv!r}: {e}") from e
    if cr != "pass":
        bx, by = board_size
        col, row0 = cr
        if not (0 <= col < bx and 0 <= row0 < by):
            raise LadderMoveError(f"search mechanism: out-of-board move {mv!r}")
    return cr


def _pick_search_move(analysis, board_size):
    infos = analysis.get("moveInfos")
    if not isinstance(infos, list) or not infos:
        raise LadderMoveError("search mechanism: missing/empty moveInfos")
    # FAIL CLOSED on ANY malformed entry — validate EVERY entry FULLY (shape + order + GTP parse +
    # board bounds) BEFORE selecting the min-order move. Do NOT skip a bad entry and select another,
    # and do NOT defer parse/bounds to only the selected entry (R6-H2/R7): a malformed non-selected
    # entry means the response is corrupt, so we must not play a "certified" move from it.
    for mi in infos:
        if not isinstance(mi, dict):
            raise LadderMoveError(f"search mechanism: non-dict moveInfo entry {mi!r}")
        mv, od = mi.get("move"), mi.get("order")
        if not (isinstance(mv, str) and mv):
            raise LadderMoveError(f"search mechanism: malformed move field {mv!r}")
        if not (_is_plain_int(od) and od >= 0):  # order must be present, plain int (not bool), >= 0
            raise LadderMoveError(f"search mechanism: malformed order {od!r}")
        _validate_gtp_on_board(mv, board_size)  # parse + bounds-check EVERY entry, not just best
    best = min(infos, key=lambda mi: mi["order"])
    return _validate_gtp_on_board(best["move"], board_size)  # already validated -> safe re-parse


def pick_ladder_move(analysis: Dict, board_size: Tuple[int, int], mechanism: str) -> Union[Tuple[int, int], str]:
    """Pure move selection shared by runtime + harness. (col,row0) bottom-origin, or 'pass'.
    Fails LOUD (LadderMoveError) when `analysis` is not a dict or the mechanism's required output
    is absent/malformed — NO silent cross-mechanism fallback (a degraded humanSL response must NOT
    become an uncalibrated 1-visit search move). Callers convert this to LadderUnavailable /
    inconclusive."""
    if not isinstance(analysis, dict):
        raise LadderMoveError(f"analysis is not a dict: {type(analysis).__name__}")
    bx, by = board_size
    if mechanism == "humansl":
        hp = analysis.get("humanPolicy")
        if not _valid_policy(hp, bx * by + 1):
            raise LadderMoveError("humansl mechanism: missing/malformed/empty humanPolicy")
        return _weighted_policy_pick(hp, board_size)
    return _pick_search_move(analysis, board_size)  # net_search / humansl_search use search output


def config_sanity_key(rung: LadderRung) -> float:
    """CONFIG sanity ordering (NON-strict; ties expected for same-profile rungs). NOT Elo."""
    if rung.mechanism == "humansl" and rung.human_sl_profile:
        tok = rung.human_sl_profile.split("_")[-1]
        base = -int(tok[:-1]) if tok.endswith("k") else int(tok[:-1])
        return base * 60.0 + math.log2(rung.max_visits) * 5.0 - (rung.root_policy_temperature - 1.0) * 20.0
    return 9 * 60.0 + math.log2(rung.max_visits) * 100.0
