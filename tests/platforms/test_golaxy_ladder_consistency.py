"""Cross-consistency between the core ladder table (katrain/core/ladder.py) and the
web-layer Golaxy AI level table (katrain/web/platforms/golaxy/engine_client.py).

Only Band B (rungs 26..36, the Golaxy-ALIGNED strong tiers 准6D..超职业) mirror Golaxy
levels — they map 1:1 to the 11 strongest GOLAXY_AI_LEVELS (准6段..星阵3星). Band A
(rungs 1..25, native humanSL ranks) and the rung-37 ceiling have NO Golaxy counterpart
(golaxy_api_level is None) and are intentionally excluded."""

from katrain.core.ladder import LADDER_RUNGS
from katrain.web.platforms.golaxy.engine_client import GOLAXY_AI_LEVELS


def test_band_b_matches_11_strongest_golaxy_levels():
    strong = list(reversed(GOLAXY_AI_LEVELS))[-11:]  # weakest-first: 准6段 ... 星阵3星
    band_b = LADDER_RUNGS[25:36]  # rungs 26..36
    assert len(band_b) == len(strong) == 11
    for rung, gx in zip(band_b, strong):
        assert (rung.golaxy_level_name, rung.golaxy_api_level, rung.display_elo, rung.ref_rank) == (
            gx["level_name"],
            gx["elo_score"],
            gx["display_elo"],
            gx["ref_rank"],
        )


def test_band_a_and_ceiling_have_no_golaxy_counterpart():
    for r in list(LADDER_RUNGS[:25]) + [LADDER_RUNGS[36]]:
        assert r.golaxy_level_name is None and r.golaxy_api_level is None
