"""棋力阶梯 strength ladder: 37 rungs of local-KataGo config + pure helpers shared by
LadderStrategy (runtime) and the calibration harness.

STRUCTURE (restructured 2026-07-21):
  * Rungs 1..25  — KataGo humanSL NATIVE ranks (20K..1K, 1D..5D), NOT benchmarked
    against Golaxy. Each rung IS a humanSL rank, played by the human net (humanv0)
    at 1 visit. Labels are the ranks themselves; no Golaxy counterpart.
  * Rungs 26..36 — Golaxy-ALIGNED strong tiers (准6D..超职业), mapped 1:1 to Golaxy
    准6段..星阵3星. net_search on the DEFAULT main net (b28). visits are PROVISIONAL
    (uncalibrated) starting points; calibration vs live Golaxy overwrites them —
    goal = >= the Golaxy level at the same label (never visibly weaker), NOT 50%.
  * Rung 37     — "KataGo中等" ceiling = b28 @ 500 visits (no Golaxy counterpart).

`net` reflects which net actually produces the move (humanv0 for humansl, b28 for
net_search); the default main net is b28. Routing a rung to the b18 main net (a
compute-saving option) would ALSO need overrideSettings.model="b18" — not wired here.
`config_sanity_key` is a CONFIG sanity ordering ONLY; real strength comes from measured
games. Band B visits are PROVISIONAL until calibrated."""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Dict, List, Mapping, Optional, Tuple, Union

MECHANISMS = ("humansl", "humansl_search", "net_search")
_COLS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"  # GTP columns, 'I' skipped

# Bumped by calibration/bake_results.py's bump_ladder_version() every time a REAL measured-Elo
# bake overwrites the table below. "v1" = PROVISIONAL, never yet measured against live Golaxy
# (Band B visits are uncalibrated starting guesses; Band A native humanSL ranks need no Golaxy
# calibration). Restructured 2026-07-21 to the 37-rung hybrid -- see the module docstring above.
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
    rank_name: str  # user-facing 段位 label (星阵-free); NEVER derived from golaxy_level_name at display time
    net: str  # v1: always 'b18' (== shipping engine)
    mechanism: str
    human_sl_profile: Optional[str]
    max_visits: int
    human_sl_params: Dict = field(default_factory=dict)
    backend_hint: str = "server"
    root_policy_temperature: float = 1.0


@dataclass(frozen=True)
class LadderStrengthSpec:
    visits: int
    main_model: Optional[str]
    human_model: Optional[str]
    override_settings: Mapping[str, object]

    def __post_init__(self):
        settings = deepcopy(dict(self.override_settings))
        if any(type(value) not in (bool, int, float, str) for value in settings.values()):
            raise ValueError("override_settings values must be immutable scalar bool/int/float/string values")
        if any(type(value) is float and not math.isfinite(value) for value in settings.values()):
            raise ValueError("override_settings numeric values must be finite")
        object.__setattr__(self, "override_settings", MappingProxyType(settings))


HUMANSL_PIKL_BASELINE = {
    "humanSLChosenMoveProp": 1.0,
    "humanSLChosenMovePiklLambda": 0.08,
    "humanSLRootExploreProbWeightless": 0.8,
    "humanSLCpuctPermanent": 2.0,
    "useUncertainty": False,
    "subtreeValueBiasFactor": 0.0,
    "useNoisePruning": False,
}

_PIKL_NUMERIC_SETTINGS = {
    "humanSLChosenMoveProp",
    "humanSLChosenMovePiklLambda",
    "humanSLRootExploreProbWeightless",
    "humanSLCpuctPermanent",
    "subtreeValueBiasFactor",
}
_PIKL_BOOLEAN_SETTINGS = {"useUncertainty", "useNoisePruning"}
_RESERVED_OVERRIDE_SETTINGS = {"model", "maxVisits"}


# ── Band A: KataGo humanSL NATIVE ranks (rungs 1..25) ─────────────────────────
# NOT benchmarked against Golaxy. Each rung IS a humanSL rank, played by the HUMAN
# net (humanv0) at 1 visit. Label = the rank; no Golaxy counterpart (golaxy_* /
# display_elo = None). The deepest kyu get a temperature bump (looser, weaker play).
_HUMANSL_NATIVE = [
    # (rank_name, humanSLProfile)
    ("20K", "rank_20k"), ("19K", "rank_19k"), ("18K", "rank_18k"), ("17K", "rank_17k"),
    ("16K", "rank_16k"), ("15K", "rank_15k"), ("14K", "rank_14k"), ("13K", "rank_13k"),
    ("12K", "rank_12k"), ("11K", "rank_11k"), ("10K", "rank_10k"), ("9K", "rank_9k"),
    ("8K", "rank_8k"), ("7K", "rank_7k"), ("6K", "rank_6k"), ("5K", "rank_5k"),
    ("4K", "rank_4k"), ("3K", "rank_3k"), ("2K", "rank_2k"), ("1K", "rank_1k"),
    ("1D", "rank_1d"), ("2D", "rank_2d"), ("3D", "rank_3d"), ("4D", "rank_4d"), ("5D", "rank_5d"),
]
_DEEP_KYU_TEMP = {"rank_20k", "rank_19k", "rank_18k", "rank_17k", "rank_16k"}  # looser weak play

# ── Band B: Golaxy-ALIGNED strong tiers (rungs 26..36) ────────────────────────
# net_search on the DEFAULT main net (b28). `max_visits` here are PROVISIONAL
# starting guesses — calibration vs live Golaxy overwrites them (goal: >= the Golaxy
# level at the same label, never visibly weaker). golaxy_api_level / display_elo /
# ref_rank mirror GOLAXY_AI_LEVELS (locked by tests/platforms/test_golaxy_ladder_consistency).
_GOLAXY_ALIGNED = [
    # (rank_name, golaxy_level_name, api_level, display_elo, ref_rank, provisional_visits)
    ("准6D", "准6段", 2200, 2200, "业余准6段", 4),
    ("6D", "6段", 2300, 2300, "业余6段", 8),
    ("准7D", "准7段", 2400, 2400, "野狐9D", 16),
    ("7D", "7段", 2500, 2500, "野狐9D", 24),
    ("准8D", "准8段", 2600, 2600, "野狐9D", 40),
    ("8D", "8段", 2800, 2800, "野狐9D", 64),
    ("准9D", "准9段", 2900, 2900, "野狐9D", 100),
    ("9D", "9段", 3000, 3100, "野狐9D", 160),
    ("职业", "星阵1星", 3100, 3400, "职业/野狐9D+", 250),
    ("职业顶尖", "星阵2星", 3200, 3700, "职业/野狐9D+", 350),
    ("超职业", "星阵3星", 3300, 4000, "职业/野狐9D+", 450),
]

# ── Ceiling: rung 37 = "KataGo中等" = b28 @ 500 visits (no Golaxy counterpart) ──
# Fixed medium-compute ceiling. OPEN QUESTION: whether b28@500 is actually >= Golaxy
# 星阵3星 (超职业, rung 36) is a calibration finding — if 超职业 needs >500 visits to
# match 星阵3星, revisit this ceiling.
_CEILING_VISITS = 500


def _build_ladder() -> List[LadderRung]:
    rungs: List[LadderRung] = []
    n = 0
    # Band A — native humanSL ranks (human net humanv0, 1 visit, no Golaxy alignment)
    for rank_name, profile in _HUMANSL_NATIVE:
        n += 1
        temp = 1.1 if profile in _DEEP_KYU_TEMP else 1.0
        rungs.append(
            LadderRung(
                rung=n, golaxy_level_name=None, golaxy_api_level=None, display_elo=None,
                ref_rank=rank_name, rank_name=rank_name, net="humanv0", mechanism="humansl",
                human_sl_profile=profile, max_visits=1, human_sl_params={},
                backend_hint="server", root_policy_temperature=temp,
            )
        )
    # Band B — Golaxy-aligned strong tiers (net_search @ default b28, provisional visits)
    for rank_name, gname, api, disp, ref, visits in _GOLAXY_ALIGNED:
        n += 1
        rungs.append(
            LadderRung(
                rung=n, golaxy_level_name=gname, golaxy_api_level=api, display_elo=disp,
                ref_rank=ref, rank_name=rank_name, net="b28", mechanism="net_search",
                human_sl_profile=None, max_visits=visits, human_sl_params={},
                backend_hint="server", root_policy_temperature=1.0,
            )
        )
    # Ceiling — rung 37 (b28 @ 500)
    n += 1
    rungs.append(
        LadderRung(
            rung=n, golaxy_level_name=None, golaxy_api_level=None, display_elo=None,
            ref_rank="天花板", rank_name="KataGo中等", net="b28", mechanism="net_search",
            human_sl_profile=None, max_visits=_CEILING_VISITS, human_sl_params={},
            backend_hint="server", root_policy_temperature=1.0,
        )
    )
    return rungs


LADDER_RUNGS: List[LadderRung] = _build_ladder()
_BY_RUNG = {r.rung: r for r in LADDER_RUNGS}


def get_rung(n: int) -> LadderRung:
    if n not in _BY_RUNG:
        raise ValueError(f"rung out of range 1..37: {n!r}")
    return _BY_RUNG[n]


def _nonempty_string(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite_number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _validate_humansl_search_recipe(params: Mapping[str, object]) -> None:
    missing = (_PIKL_NUMERIC_SETTINGS | _PIKL_BOOLEAN_SETTINGS) - params.keys()
    if missing:
        raise ValueError(f"humansl_search missing required settings: {sorted(missing)}")
    for key in _PIKL_NUMERIC_SETTINGS:
        value = params[key]
        if not _finite_number(value):
            raise ValueError(f"humansl_search setting {key} must be a finite number")
    for key in _PIKL_BOOLEAN_SETTINGS:
        if type(params[key]) is not bool:
            raise ValueError(f"humansl_search setting {key} must be a bool")
    if not 0 < params["humanSLChosenMoveProp"] <= 1:
        raise ValueError("humanSLChosenMoveProp must be in the range (0, 1]")
    if not 0 < params["humanSLChosenMovePiklLambda"] <= 1_000_000_000:
        raise ValueError("humanSLChosenMovePiklLambda must be in the range (0, 1e9]")
    if not 0 < params["humanSLRootExploreProbWeightless"] <= 1:
        raise ValueError("humanSLRootExploreProbWeightless must be in the range (0, 1]")
    if not 0 < params["humanSLCpuctPermanent"] <= 1000:
        raise ValueError("humanSLCpuctPermanent must be in the range (0, 1000]")
    if not 0 <= params["subtreeValueBiasFactor"] <= 1:
        raise ValueError("subtreeValueBiasFactor must be in the range [0, 1]")


def rung_strength_spec(rung: LadderRung) -> LadderStrengthSpec:
    """Return a validated, immutable description of the engine strength request."""
    if rung.mechanism not in MECHANISMS:
        raise ValueError(f"invalid ladder mechanism: {rung.mechanism!r}")
    if not _is_plain_int(rung.max_visits) or rung.max_visits <= 0:
        raise ValueError(f"max_visits must be a positive plain int: {rung.max_visits!r}")
    if not _nonempty_string(rung.net):
        raise ValueError(f"rung net must be a nonempty model name: {rung.net!r}")
    if not _finite_number(rung.root_policy_temperature) or rung.root_policy_temperature <= 0:
        raise ValueError(f"root_policy_temperature must be a positive finite number: {rung.root_policy_temperature!r}")
    if not isinstance(rung.human_sl_params, Mapping):
        raise ValueError("human_sl_params must be a mapping")
    params = deepcopy(dict(rung.human_sl_params))
    if any(type(value) not in (bool, int, float, str) for value in params.values()):
        raise ValueError("human_sl_params values must be immutable scalar bool/int/float/string values")
    if any(type(value) is float and not math.isfinite(value) for value in params.values()):
        raise ValueError("human_sl_params numeric values must be finite")
    reserved = _RESERVED_OVERRIDE_SETTINGS & params.keys()
    if reserved:
        raise ValueError(f"reserved settings do not belong in human_sl_params: {sorted(reserved)}")

    if rung.mechanism == "humansl":
        if not _nonempty_string(rung.human_sl_profile):
            raise ValueError("humansl requires a nonempty HumanSL profile")
        if rung.net != "humanv0" or rung.max_visits != 1:
            raise ValueError("humansl requires humanv0 at exactly one visit")
        if params:
            raise ValueError("humansl requires empty human_sl_params")
        main_model, human_model = None, "humanv0"
    elif rung.mechanism == "net_search":
        if rung.human_sl_profile is not None or params:
            raise ValueError("net_search must not carry a HumanSL profile or parameters")
        main_model, human_model = rung.net, None
    else:
        if not _nonempty_string(rung.human_sl_profile):
            raise ValueError("humansl_search requires a nonempty HumanSL profile")
        if rung.net == "humanv0":
            raise ValueError("humansl_search must use a non-human main search model")
        _validate_humansl_search_recipe(params)
        main_model, human_model = rung.net, "humanv0"

    ov: Dict = {"reportAnalysisWinratesAs": "BLACK"}
    if rung.human_sl_profile:
        ov["humanSLProfile"] = rung.human_sl_profile
        ov["ignorePreRootHistory"] = False
    if abs(rung.root_policy_temperature - 1.0) > 1e-9:
        ov["rootPolicyTemperature"] = rung.root_policy_temperature
    ov.update(params)
    return LadderStrengthSpec(rung.max_visits, main_model, human_model, ov)


def ladder_override_settings(rung: LadderRung) -> Dict:
    """Compatibility projection of the canonical native KataGo overrides."""
    return deepcopy(dict(rung_strength_spec(rung).override_settings))


def rung_engine_params(rung: LadderRung) -> Dict:
    """Compatibility projection; model identities remain outside overrideSettings."""
    spec = rung_strength_spec(rung)
    return {
        "visits": spec.visits,
        "extra_settings": deepcopy(dict(spec.override_settings)),
        "main_model": spec.main_model,
        "human_model": spec.human_model,
    }


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
