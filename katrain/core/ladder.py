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

import hashlib
import json
import math
import os
from copy import deepcopy
from dataclasses import dataclass, field, fields
from fractions import Fraction
from types import MappingProxyType
from typing import Dict, FrozenSet, List, Mapping, Optional, Tuple, Union

MECHANISMS = ("humansl", "humansl_search", "net_search")
HUMAN_WEIGHTED = "human_weighted"
HUMAN_TEMPERATURE = "human_temperature"
HUMAN_ARGMAX = "human_argmax"
SEARCH = "search"
NATIVE_POLICY_ARGMAX = "native_policy_argmax"
LADDER_SELECTIONS = {HUMAN_WEIGHTED, HUMAN_TEMPERATURE, HUMAN_ARGMAX, SEARCH, NATIVE_POLICY_ARGMAX}
_COLS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"  # GTP columns, 'I' skipped
TEMPERATURE_MIN = 0.05
TEMPERATURE_MAX = 10.0
_U64_MAX = 2**64 - 1

# Bumped by calibration/bake_results.py's bump_ladder_version() every time a REAL measured-Elo
# bake overwrites the table below. "v1" = PROVISIONAL, never yet measured against live Golaxy
# (Band B visits are uncalibrated starting guesses; Band A native humanSL ranks need no Golaxy
# calibration). Restructured 2026-07-21 to the 37-rung hybrid -- see the module docstring above.
LADDER_VERSION = "v1"


class LadderMoveError(Exception):
    """A rung's required analysis output is absent/malformed, so no certified move can be
    selected. Callers MUST NOT substitute an uncalibrated move: LadderStrategy converts this
    to LadderUnavailable (no move); the calibration harness converts it to an inconclusive game."""


class LadderUnavailable(ValueError):
    """The requested product level has no certified, available executable recipe."""


class _FrozenMapping(Mapping[str, object]):
    """Small immutable mapping which remains compatible with dataclasses.asdict()."""

    def __init__(self, values):
        self._values = deepcopy(dict(values))

    def __getitem__(self, key):
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __deepcopy__(self, memo):
        return deepcopy(self._values, memo)


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
    human_sl_params: Mapping[str, object] = field(default_factory=dict)
    backend_hint: str = "server"
    root_policy_temperature: float = 1.0
    human_policy_temperature: Optional[float] = None
    selection: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.human_sl_params, Mapping):
            raise TypeError("human_sl_params must be a mapping")
        object.__setattr__(self, "human_sl_params", _FrozenMapping(self.human_sl_params))

    def to_dict(self) -> Dict[str, object]:
        """Return a mutable serialization without exposing the frozen recipe mapping."""
        return {
            item.name: (
                deepcopy(dict(self.human_sl_params))
                if item.name == "human_sl_params"
                else deepcopy(getattr(self, item.name))
            )
            for item in fields(self)
        }


@dataclass(frozen=True)
class LadderLevel:
    rung: int
    rank_name: str
    recipe: Optional[LadderRung]
    candidate_labels: Tuple[str, ...]
    certification_status: str
    availability: str
    route: str
    external_status: str

    def __post_init__(self):
        allowed = {
            "certification_status": {"provisional", "certified"},
            "availability": {"available", "unavailable"},
            "route": {"local", "server"},
            "external_status": {
                "not_applicable",
                "untested",
                "screened",
                "aligned",
                "overstrong",
                "understrong",
                "incomplete",
            },
        }
        for field_name, values in allowed.items():
            value = getattr(self, field_name)
            if value not in values:
                raise ValueError(f"invalid {field_name}: {value!r}; expected one of {sorted(values)}")
        if type(self.rung) is not int or not 1 <= self.rung <= 41:
            raise ValueError(f"level rung out of range 1..41: {self.rung!r}")
        if not _nonempty_string(self.rank_name):
            raise ValueError("level rank_name must be a nonempty string")
        if type(self.candidate_labels) is not tuple or any(
            not _nonempty_string(label) for label in self.candidate_labels
        ):
            raise ValueError("candidate_labels must be a tuple of nonempty strings")


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


HUMANSL_PIKL_BASELINE_V1 = MappingProxyType(
    {
        "humanSLChosenMoveProp": 1.0,
        "humanSLChosenMovePiklLambda": 0.08,
        "humanSLRootExploreProbWeightless": 0.8,
        "humanSLCpuctPermanent": 2.0,
        "useUncertainty": False,
        "subtreeValueBiasFactor": 0.0,
        "useNoisePruning": False,
    }
)
HUMANSL_PIKL_BASELINE = HUMANSL_PIKL_BASELINE_V1

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
    ("20K", "rank_20k"),
    ("19K", "rank_19k"),
    ("18K", "rank_18k"),
    ("17K", "rank_17k"),
    ("16K", "rank_16k"),
    ("15K", "rank_15k"),
    ("14K", "rank_14k"),
    ("13K", "rank_13k"),
    ("12K", "rank_12k"),
    ("11K", "rank_11k"),
    ("10K", "rank_10k"),
    ("9K", "rank_9k"),
    ("8K", "rank_8k"),
    ("7K", "rank_7k"),
    ("6K", "rank_6k"),
    ("5K", "rank_5k"),
    ("4K", "rank_4k"),
    ("3K", "rank_3k"),
    ("2K", "rank_2k"),
    ("1K", "rank_1k"),
    ("1D", "rank_1d"),
    ("2D", "rank_2d"),
    ("3D", "rank_3d"),
    ("4D", "rank_4d"),
    ("5D", "rank_5d"),
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
                rung=n,
                golaxy_level_name=None,
                golaxy_api_level=None,
                display_elo=None,
                ref_rank=rank_name,
                rank_name=rank_name,
                net="humanv0",
                mechanism="humansl",
                human_sl_profile=profile,
                max_visits=1,
                selection=HUMAN_WEIGHTED,
                human_sl_params={},
                backend_hint="server",
                root_policy_temperature=temp,
            )
        )
    # Band B — Golaxy-aligned strong tiers (net_search @ default b28, provisional visits)
    for rank_name, gname, api, disp, ref, visits in _GOLAXY_ALIGNED:
        n += 1
        rungs.append(
            LadderRung(
                rung=n,
                golaxy_level_name=gname,
                golaxy_api_level=api,
                display_elo=disp,
                ref_rank=ref,
                rank_name=rank_name,
                net="b28",
                mechanism="net_search",
                human_sl_profile=None,
                max_visits=visits,
                selection=SEARCH,
                human_sl_params={},
                backend_hint="server",
                root_policy_temperature=1.0,
            )
        )
    # Ceiling — rung 37 (b28 @ 500)
    n += 1
    rungs.append(
        LadderRung(
            rung=n,
            golaxy_level_name=None,
            golaxy_api_level=None,
            display_elo=None,
            ref_rank="天花板",
            rank_name="KataGo中等",
            net="b28",
            mechanism="net_search",
            human_sl_profile=None,
            max_visits=_CEILING_VISITS,
            selection=SEARCH,
            human_sl_params={},
            backend_hint="server",
            root_policy_temperature=1.0,
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
    return type(value) is int or (type(value) is float and math.isfinite(value))


_LEVEL_NAMES = (
    *(f"{rank}级" for rank in range(20, 0, -1)),
    *(label for rank in range(1, 10) for label in (f"准{rank}段", f"{rank}段")),
    "职业水平",
    "职业顶尖",
    "超越人类",
)
_TEMPERATURE_CANDIDATES = ("t1.15", "t1.3", "t1.6", "t2", "t2.5", "t3")
_QUASI_9_CANDIDATES = ("rank_9d@1", "rank_9d@1s", "rank_9d@2", "rank_9d@3")
_PRO_TOP_CANDIDATES = ("b18@12", "b18@10", "b18@14", "b18@8", "b18@16")


def _recipe(
    rung: int,
    rank_name: str,
    *,
    net: str,
    mechanism: str,
    profile: Optional[str],
    visits: int,
    selection: str,
    human_sl_params: Mapping[str, object] = MappingProxyType({}),
    golaxy_level_name: Optional[str] = None,
    golaxy_api_level: Optional[int] = None,
) -> LadderRung:
    return LadderRung(
        rung=rung,
        golaxy_level_name=golaxy_level_name,
        golaxy_api_level=golaxy_api_level,
        display_elo=golaxy_api_level,
        ref_rank=profile or rank_name,
        rank_name=rank_name,
        net=net,
        mechanism=mechanism,
        human_sl_profile=profile,
        max_visits=visits,
        human_sl_params=human_sl_params,
        backend_hint="server",
        root_policy_temperature=1.0,
        selection=selection,
    )


def _fixed_product_recipe(rung: int, rank_name: str) -> Optional[LadderRung]:
    if 1 <= rung <= 20:
        rank = 21 - rung
        api_level = None if rank >= 19 else (220 if rank == 18 else 1100 - (rank - 1) * 100)
        return _recipe(
            rung,
            rank_name,
            net="humanv0",
            mechanism="humansl",
            profile=f"rank_{rank}k",
            visits=1,
            selection=HUMAN_WEIGHTED,
            golaxy_level_name=rank_name if api_level is not None else None,
            golaxy_api_level=api_level,
        )
    if rung in (22, 24, 26, 28, 30, 32):
        rank = (rung - 20) // 2
        return _recipe(
            rung,
            rank_name,
            net="humanv0",
            mechanism="humansl",
            profile=f"rank_{rank}d",
            visits=1,
            selection=HUMAN_WEIGHTED,
            golaxy_level_name=rank_name,
            golaxy_api_level=1100 + rank * 200,
        )
    if rung in (34, 36):
        rank = 7 if rung == 34 else 8
        return _recipe(
            rung,
            rank_name,
            net="humanv0",
            mechanism="humansl",
            profile=f"rank_{rank}d",
            visits=1,
            selection=HUMAN_ARGMAX,
            golaxy_level_name=rank_name,
            golaxy_api_level=2500 if rank == 7 else 2800,
        )
    if rung == 38:
        return _recipe(
            rung,
            rank_name,
            net="b18",
            mechanism="humansl_search",
            profile="rank_9d",
            visits=4,
            selection=SEARCH,
            human_sl_params=HUMANSL_PIKL_BASELINE_V1,
            golaxy_level_name="9段",
            golaxy_api_level=3000,
        )
    if rung == 39:
        return _recipe(
            rung,
            rank_name,
            net="b18",
            mechanism="net_search",
            profile=None,
            visits=1,
            selection=NATIVE_POLICY_ARGMAX,
            golaxy_level_name="星阵1星",
            golaxy_api_level=3100,
        )
    if rung == 41:
        return _recipe(
            rung,
            rank_name,
            net="b18",
            mechanism="net_search",
            profile=None,
            visits=64,
            selection=SEARCH,
            golaxy_level_name="星阵3星",
            golaxy_api_level=3300,
        )
    return None


def _candidate_labels(rung: int) -> Tuple[str, ...]:
    if rung in (21, 23, 25, 27, 29, 31, 33, 35):
        return _TEMPERATURE_CANDIDATES
    if rung == 37:
        return _QUASI_9_CANDIDATES
    if rung == 40:
        return _PRO_TOP_CANDIDATES
    return ()


#: Rungs whose strength configuration has passed formal adjacent verification.
#: Empty until it has. Adding a rung here is a product claim: it says this level's
#: recipe was verified against its neighbours under a frozen batch, and every entry
#: must cite the EXPERIMENTS.md section that verified it. Never widen this set to
#: make something playable -- that is what LADDER_ALLOW_PROVISIONAL_ENV is for, and
#: that switch never touches what the API reports.
_CERTIFIED_RUNGS: FrozenSet[int] = frozenset()

#: Development-only escape hatch. When set to "1", `resolve_available_rung` will
#: hand back the recipe for a provisional rung so the rated-play pipeline can be
#: exercised end to end before calibration lands. It deliberately does NOT alter
#: `certification_status` / `availability`: the API keeps reporting the truth and
#: the UI keeps showing the 未标定 badge. An environment variable rather than a
#: config key, because `--ui web` rewrites ~/.katrain/config.json on exit.
LADDER_ALLOW_PROVISIONAL_ENV = "KATRAIN_LADDER_ALLOW_PROVISIONAL"


def _level_certification(rung: int, recipe: Optional[LadderRung]) -> Tuple[str, str]:
    certified = recipe is not None and rung in _CERTIFIED_RUNGS
    return ("certified", "available") if certified else ("provisional", "unavailable")


def _build_levels() -> Tuple[LadderLevel, ...]:
    levels = []
    for rung, rank_name in enumerate(_LEVEL_NAMES, start=1):
        recipe = _fixed_product_recipe(rung, rank_name)
        certification_status, availability = _level_certification(rung, recipe)
        levels.append(
            LadderLevel(
                rung=rung,
                rank_name=rank_name,
                recipe=recipe,
                candidate_labels=_candidate_labels(rung),
                certification_status=certification_status,
                availability=availability,
                route="server",
                external_status="not_applicable" if rung <= 2 else "untested",
            )
        )
    return tuple(levels)


LADDER_LEVELS = _build_levels()


#: The rungs a player can actually be seated on. Ten of the 41 (准1段–准9段 and
#: 职业顶尖) never had a strength recipe fitted, so they are names on the ladder
#: with nothing behind them. Anything that MOVES a player -- promotion, demotion,
#: the landing of a placement search -- has to step over them, otherwise it parks
#: someone on a rung no opponent can ever be built for.
PLAYABLE_RUNGS: Tuple[int, ...] = tuple(level.rung for level in LADDER_LEVELS if level.recipe is not None)


def get_level(n: int) -> LadderLevel:
    if type(n) is not int or not 1 <= n <= len(LADDER_LEVELS):
        raise ValueError(f"level out of range 1..41: {n!r}")
    return LADDER_LEVELS[n - 1]


def nearest_playable_rung(n: int) -> int:
    """The playable rung closest to `n`, preferring the lower one on a tie.

    Used when a rung arrives from outside this module (a stored value, a search
    landing) and may point at one of the ten recipe-less rungs.
    """
    if type(n) is not int or not 1 <= n <= len(LADDER_LEVELS):
        raise ValueError(f"level out of range 1..41: {n!r}")
    return min(PLAYABLE_RUNGS, key=lambda rung: (abs(rung - n), rung))


def step_playable_rung(n: int, step: int) -> int:
    """Move `step` playable rungs from `n`, saturating at both ends.

    `step` counts rungs a player can be seated on, not raw catalog positions:
    5段(30) + 1 is 6段(32), because 准6段(31) has no recipe. Arithmetic on the raw
    rung number lands on 31 and seats the player where no game can be played.
    """
    if type(step) is not int:
        raise ValueError(f"step must be an integer: {step!r}")
    start = nearest_playable_rung(n)
    index = PLAYABLE_RUNGS.index(start) + step
    index = max(0, min(index, len(PLAYABLE_RUNGS) - 1))
    return PLAYABLE_RUNGS[index]


def get_recipe_for_calibration(n: int) -> LadderRung:
    level = get_level(n)
    if level.recipe is None:
        raise LadderUnavailable(f"level {n} ({level.rank_name}) has an unresolved recipe")
    return level.recipe


def provisional_play_allowed() -> bool:
    """Whether uncertified rungs may be seated. Read per call, never cached, so a
    deployment can never end up permanently permissive from a stale import."""
    return os.environ.get(LADDER_ALLOW_PROVISIONAL_ENV) == "1"


def resolve_available_rung(n: int) -> LadderRung:
    level = get_level(n)
    if level.recipe is None:
        # No amount of dev switching conjures a recipe that was never fitted.
        raise LadderUnavailable(f"level {n} ({level.rank_name}) has an unresolved recipe")
    if level.certification_status != "certified" or level.availability != "available":
        if not provisional_play_allowed():
            raise LadderUnavailable(f"level {n} ({level.rank_name}) is not certified and available")
    return level.recipe


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
    if rung.selection not in LADDER_SELECTIONS:
        raise ValueError(f"invalid or unresolved ladder selection: {rung.selection!r}")
    if not _is_plain_int(rung.max_visits) or rung.max_visits <= 0:
        raise ValueError(f"max_visits must be a positive plain int: {rung.max_visits!r}")
    if not _nonempty_string(rung.net):
        raise ValueError(f"rung net must be a nonempty model name: {rung.net!r}")
    if not _finite_number(rung.root_policy_temperature) or rung.root_policy_temperature <= 0:
        raise ValueError(f"root_policy_temperature must be a positive finite number: {rung.root_policy_temperature!r}")
    if rung.human_policy_temperature is not None:
        _validate_temperature(rung.human_policy_temperature)
        if rung.mechanism != "humansl" or rung.selection != HUMAN_TEMPERATURE:
            raise ValueError("human_policy_temperature is only valid for humansl human_temperature selection")
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
        if rung.selection not in (HUMAN_WEIGHTED, HUMAN_TEMPERATURE, HUMAN_ARGMAX):
            raise ValueError("humansl requires a human-policy selection")
        if rung.selection == HUMAN_TEMPERATURE and rung.human_policy_temperature is None:
            raise ValueError("human_temperature requires human_policy_temperature")
        main_model, human_model = None, "humanv0"
    elif rung.mechanism == "net_search":
        if rung.human_sl_profile is not None or params:
            raise ValueError("net_search must not carry a HumanSL profile or parameters")
        if rung.selection not in (SEARCH, NATIVE_POLICY_ARGMAX):
            raise ValueError("net_search requires search or native_policy_argmax selection")
        if rung.selection == NATIVE_POLICY_ARGMAX and rung.max_visits != 1:
            raise ValueError("native_policy_argmax requires a pure main-model one-visit recipe")
        main_model, human_model = rung.net, None
    else:
        if not _nonempty_string(rung.human_sl_profile):
            raise ValueError("humansl_search requires a nonempty HumanSL profile")
        if rung.net == "humanv0":
            raise ValueError("humansl_search must use a non-human main search model")
        if rung.selection != SEARCH:
            raise ValueError("humansl_search requires search selection")
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


def _strict_canonical_json_value(value, path="root"):
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a nonfinite number")
        if value == 0 or value.is_integer():
            return int(value)
        return value
    if isinstance(value, list):
        return [_strict_canonical_json_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, Mapping):
        normalized = {}
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError(f"{path} contains a non-string mapping key: {key!r}")
            normalized[key] = _strict_canonical_json_value(item, f"{path}.{key}")
        return normalized
    raise ValueError(f"{path} contains an unsupported strict JSON value: {type(value).__name__}")


def rung_endpoint_digest(rung: LadderRung, model_identity: Mapping[str, object]) -> str:
    """Digest the fully resolved effective strength and selection recipe using canonical JSON."""
    spec = rung_strength_spec(rung)
    if not isinstance(model_identity, Mapping):
        raise ValueError("model_identity must be a mapping")
    effective_overrides = dict(spec.override_settings)
    payload = _strict_canonical_json_value(
        {
            "schema": "ladder-endpoint-v1",
            "model_identity": model_identity,
            "mechanism": rung.mechanism,
            "selection": rung.selection,
            "visits": spec.visits,
            "main_model": spec.main_model,
            "human_model": spec.human_model,
            "human_sl_profile": effective_overrides.get("humanSLProfile"),
            "human_policy_temperature": rung.human_policy_temperature,
            "root_policy_temperature": effective_overrides.get("rootPolicyTemperature", 1.0),
            "override_settings": effective_overrides,
        }
    )
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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


_ATTESTATION_IDENTITY_FIELDS = (
    "selected_model",
    "model_path",
    "model_sha256",
    "human_model_path",
    "human_model_sha256",
    "katago_version",
)


def validate_analysis_attestation(
    analysis: Mapping[str, object],
    spec: LadderStrengthSpec,
    capability_identity: Optional[Mapping[str, object]] = None,
) -> None:
    """Validate the HTTP wrapper's executed-model identity for a certified ladder query.

    Native HumanSL at one visit has no explicit main-model route and therefore needs no
    wrapper attestation. Every explicitly routed search must attest both what was requested
    and the immutable identity retained from wrapper startup health.
    """
    if spec.main_model is None:
        return
    if not isinstance(analysis, Mapping):
        raise LadderMoveError("analysis attestation: analysis is not a mapping")
    wrapper = analysis.get("_wrapper")
    if not isinstance(wrapper, Mapping):
        raise LadderMoveError("analysis attestation: missing/malformed _wrapper identity")
    if wrapper.get("selected_model") != spec.main_model:
        raise LadderMoveError(
            f"analysis attestation selected_model mismatch: expected {spec.main_model!r}, "
            f"got {wrapper.get('selected_model')!r}"
        )

    required_response_fields = ["model_path", "model_sha256", "katago_version"]
    if spec.human_model is not None:
        required_response_fields.extend(("human_model_path", "human_model_sha256"))
    for field_name in required_response_fields:
        if not isinstance(wrapper.get(field_name), str) or not wrapper[field_name]:
            raise LadderMoveError(f"analysis attestation {field_name} is missing/malformed")

    if not isinstance(capability_identity, Mapping):
        raise LadderMoveError("analysis attestation: missing retained startup capability identity")
    for field_name in _ATTESTATION_IDENTITY_FIELDS:
        expected = capability_identity.get(field_name)
        actual = wrapper.get(field_name)
        if actual != expected:
            raise LadderMoveError(f"analysis attestation {field_name} mismatch: expected {expected!r}, got {actual!r}")


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


def _validate_temperature(temperature: float) -> None:
    if not _finite_number(temperature) or not TEMPERATURE_MIN <= temperature <= TEMPERATURE_MAX:
        raise ValueError(
            f"temperature must be a finite non-boolean number in [{TEMPERATURE_MIN}, {TEMPERATURE_MAX}]: "
            f"{temperature!r}"
        )


def temperature_policy_distribution(human_policy, temperature: float) -> List[float]:
    """Return normalized HumanSL policy weights transformed by ``p ** (1 / temperature)``."""
    _validate_temperature(temperature)
    if not isinstance(human_policy, list) or not human_policy:
        raise ValueError("human_policy must be a nonempty list")
    if any(not _finite_number(value) for value in human_policy):
        raise ValueError("human_policy entries must be finite non-boolean numbers")

    positive_logs = [math.log(value) for value in human_policy if value > 0]
    if not positive_logs:
        raise ValueError("human_policy must contain at least one positive entry")
    max_scaled_log = max(positive_logs) / temperature
    weights = [math.exp(math.log(value) / temperature - max_scaled_log) if value > 0 else 0.0 for value in human_policy]
    total = math.fsum(weights)
    return [weight / total for weight in weights]


def policy_index_to_gtp(index: int) -> str:
    """Convert a 19x19 KataGo policy index to canonical uppercase GTP (or ``pass``)."""
    if not _is_plain_int(index) or not 0 <= index <= 361:
        raise ValueError(f"policy index must be a plain int in 0..361: {index!r}")
    if index == 361:
        return "pass"
    x = index % 19
    row0 = 18 - index // 19
    return colrow_to_gtp(x, row0)


def pick_temperature_policy(human_policy, board_size, temperature: float, draw_u64: int):
    """Select from a temperature-adjusted HumanSL policy with one explicit unsigned 64-bit draw.

    Returns ``((column, bottom-origin-row), policy_index)`` or ``("pass", policy_index)``.
    """
    try:
        if not _is_plain_int(draw_u64) or not 0 <= draw_u64 <= _U64_MAX:
            raise ValueError(f"draw_u64 must be a plain unsigned 64-bit integer: {draw_u64!r}")
        if (
            not isinstance(board_size, tuple)
            or len(board_size) != 2
            or any(not _is_plain_int(size) or size <= 0 for size in board_size)
        ):
            raise ValueError(f"board_size must be a pair of positive plain ints: {board_size!r}")
        bx, by = board_size
        if not isinstance(human_policy, list):
            raise ValueError("human_policy must be a list")
        if len(human_policy) != bx * by + 1:
            raise ValueError(f"human_policy must have exactly {bx * by + 1} entries")
        weights = temperature_policy_distribution(human_policy, temperature)
    except ValueError as exc:
        raise LadderMoveError(f"temperature policy selection: {exc}") from exc

    candidates = []
    for x in range(bx):
        for y in range(by):
            index = (by - y - 1) * bx + x
            if weights[index] > 0:
                candidates.append(((x, y), index, weights[index]))
    if weights[-1] > 0:
        candidates.append(("pass", len(weights) - 1, weights[-1]))

    total = math.fsum(weight for _, _, weight in candidates)
    target = Fraction(2 * draw_u64 + 1, 2**65) * Fraction.from_float(total)
    cumulative = 0.0
    for move, index, weight in candidates:
        cumulative += weight
        # Algebraically equivalent to cumulative > ((draw + 0.5) / 2**64) * total,
        # without rounding the half-step away at exact inverse-CDF boundaries.
        if Fraction.from_float(cumulative) > target:
            return move, index
    move, index, _ = candidates[-1]
    return move, index


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


def _valid_ladder_policy(policy, expected_len) -> bool:
    return (
        isinstance(policy, list)
        and len(policy) == expected_len
        and all(_finite_number(value) for value in policy)
        and sum(value for value in policy if value > 0) > 0
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


def _pick_policy_argmax(policy, board_size, field_name):
    try:
        if (
            not isinstance(board_size, tuple)
            or len(board_size) != 2
            or any(not _is_plain_int(size) or size <= 0 for size in board_size)
        ):
            raise ValueError(f"board_size must be a pair of positive plain ints: {board_size!r}")
        bx, by = board_size
        if not _valid_ladder_policy(policy, bx * by + 1):
            raise ValueError(f"{field_name} must be a valid {bx * by + 1}-entry policy")
    except ValueError as exc:
        raise LadderMoveError(f"{field_name} argmax selection: {exc}") from exc

    candidates = []
    for x in range(bx):
        for y in range(by):
            index = (by - y - 1) * bx + x
            candidates.append((policy[index], (x, y)))
    candidates.append((policy[-1], "pass"))
    return max(candidates, key=lambda candidate: candidate[0])[1]


def pick_ladder_rung_move(analysis, rung: LadderRung, board_size, *, draw_u64=None):
    """Pick one certified move using the selection semantics bound into ``rung``."""
    try:
        rung_strength_spec(rung)
    except ValueError as exc:
        raise LadderMoveError(f"invalid ladder rung recipe: {exc}") from exc
    if not isinstance(analysis, dict):
        raise LadderMoveError(f"analysis is not a dict: {type(analysis).__name__}")

    if rung.selection in (HUMAN_WEIGHTED, HUMAN_TEMPERATURE):
        temperature = 1.0 if rung.selection == HUMAN_WEIGHTED else rung.human_policy_temperature
        move, _ = pick_temperature_policy(analysis.get("humanPolicy"), board_size, temperature, draw_u64)
        return move
    if rung.selection == HUMAN_ARGMAX:
        return _pick_policy_argmax(analysis.get("humanPolicy"), board_size, "humanPolicy")
    if rung.selection == NATIVE_POLICY_ARGMAX:
        root_info = analysis.get("rootInfo")
        if not isinstance(root_info, dict) or not _is_plain_int(root_info.get("visits")) or root_info["visits"] != 1:
            raise LadderMoveError("native_policy_argmax requires rootInfo.visits exactly plain int 1")
        if analysis.get("moveInfos") != [] or not isinstance(analysis.get("moveInfos"), list):
            raise LadderMoveError("native_policy_argmax requires moveInfos exactly []")
        return _pick_policy_argmax(analysis.get("policy"), board_size, "policy")
    return _pick_search_move(analysis, board_size)


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
