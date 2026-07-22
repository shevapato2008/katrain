"""Player construction boundary for the Golaxy 9D HumanSL alignment experiment.

This task intentionally contains no CLI or live-service calls. Later runner work consumes the
strict move and adjudication helpers exposed here after performing its source/engine preflight.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

sys.path.insert(0, str(Path(__file__).parent))
import golaxy_9d_alignment  # noqa: E402
import run_selfplay  # noqa: E402

from katrain.core.ladder import (  # noqa: E402
    HUMANSL_PIKL_BASELINE,
    LadderRung,
    LadderStrengthSpec,
    get_rung,
    rung_strength_spec,
)

_BOARD_SIZE = 19
_KOMI = 7.5
_RULES = "chinese"
_WIDE_ROOT_NOISE = 0.04


def _expected_strength_spec(player: str) -> LadderStrengthSpec:
    visits_text = player.removeprefix("rank_9d@").removesuffix("s")
    visits = int(visits_text)
    overrides = {
        "reportAnalysisWinratesAs": "BLACK",
        "humanSLProfile": "rank_9d",
        "ignorePreRootHistory": False,
    }
    if visits == 1:
        return LadderStrengthSpec(visits=1, main_model=None, human_model="humanv0", override_settings=overrides)
    overrides.update(HUMANSL_PIKL_BASELINE)
    return LadderStrengthSpec(visits=visits, main_model="b18", human_model="humanv0", override_settings=overrides)


def _validate_effective_query(rung: LadderRung, expected: LadderStrengthSpec) -> None:
    query = run_selfplay.adapters.build_ladder_analysis_query([], rung, _BOARD_SIZE, _KOMI, _RULES, _WIDE_ROOT_NOISE)
    expected_overrides = dict(expected.override_settings)
    expected_overrides["wideRootNoise"] = _WIDE_ROOT_NOISE
    if expected.main_model is not None:
        expected_overrides["model"] = expected.main_model
    expected_query = {
        "rules": run_selfplay.adapters.BaseEngine.get_rules(_RULES),
        "boardXSize": _BOARD_SIZE,
        "boardYSize": _BOARD_SIZE,
        "komi": _KOMI,
        "moves": [],
        "analyzeTurns": [0],
        "maxVisits": expected.visits,
        "includePolicy": True,
        "includeOwnership": False,
        "overrideSettings": expected_overrides,
    }
    if query != expected_query:
        raise ValueError("alignment player effective query drifted from the frozen grid")


def make_alignment_player(player: str) -> Tuple[str, LadderRung, str]:
    """Construct and independently validate one player from the frozen alignment grid."""
    player = golaxy_9d_alignment.validate_player_spec(player)
    label, rung, selection = run_selfplay.make_player(player, experimental_min_humansl_search_visits=2)
    expected = _expected_strength_spec(player)
    try:
        actual = rung_strength_spec(rung)
    except ValueError as exc:
        raise ValueError(f"alignment player strength spec is invalid: {exc}") from exc
    expected_selection = "argmax_human" if expected.visits == 1 else "search"
    if label != player or actual != expected or selection != expected_selection:
        raise ValueError("alignment player strength spec drifted from the frozen grid")
    _validate_effective_query(rung, expected)
    return label, rung, selection


def golaxy_9d_opponent() -> LadderRung:
    """Return rung 33 solely as the immutable Golaxy level-3000 opponent descriptor."""
    rung = get_rung(33)
    if rung.golaxy_api_level != golaxy_9d_alignment.GOLAXY_API_LEVEL:
        raise ValueError("Golaxy 9D opponent descriptor drifted from API level 3000")
    return rung


player_move_strict = run_selfplay.player_move_strict
