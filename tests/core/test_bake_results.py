import sys, importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / ".." / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"))
bake = importlib.import_module("bake_results")


def test_correction_is_per_band():
    corr = bake.banded_correction(
        [
            {"band": "kyu", "rung": 12, "elo_diff": +120},
            {"band": "amateur", "rung": 28, "elo_diff": -80},
            {"band": "super", "rung": 39, "elo_diff": +30},
        ]
    )
    assert corr["kyu"]["offset"] != corr["amateur"]["offset"]


def test_classify_tie_and_reversal():
    # overlapping CIs -> tie; strictly lower-with-gap despite higher label -> reversed
    st = bake.classify_pairs(
        [
            {"rung": 1, "elo": 0, "lo": -60, "hi": 60},
            {"rung": 2, "elo": 10, "lo": -50, "hi": 70},  # overlaps rung1 -> tie
            {"rung": 3, "elo": -200, "lo": -260, "hi": -140},  # below, no overlap -> reversed
        ]
    )
    assert st[(1, 2)] == "tie" and st[(2, 3)] == "reversed"


def test_apply_corrections_preserves_strict_monotonicity():
    """apply_corrections must never let a bake-induced knob shift regress the config-sanity
    ordering: after applying a deliberately lopsided, opposite-signed per-band correction to
    the full 40-rung table (exactly the shape of correction that COULD invert adjacent rungs
    if not clamped), bake.rung_proxy (an alias for katrain.core.ladder.config_sanity_key) must
    stay non-decreasing weak->strong -- the same invariant tests/core/test_ladder.py's
    test_config_key_non_decreasing already guards pre-bake."""
    from katrain.core.ladder import LADDER_RUNGS

    corr = bake.banded_correction(
        [
            {"band": "kyu", "rung": 5, "elo_diff": +400},
            {"band": "amateur", "rung": 20, "elo_diff": -400},
            {"band": "pro", "rung": 36, "elo_diff": +300},
            {"band": "super", "rung": 39, "elo_diff": -300},
        ]
    )
    new_rungs = bake.apply_corrections(LADDER_RUNGS, corr)
    assert len(new_rungs) == len(LADDER_RUNGS)
    proxies = [bake.rung_proxy(r) for r in new_rungs]
    for i in range(1, len(proxies)):
        assert (
            proxies[i] >= proxies[i - 1] - 1e-9
        ), f"config regressed at rung {new_rungs[i].rung} ({new_rungs[i].golaxy_level_name})"
