"""Task 6: cross-consistency between the core ladder table (katrain/core/ladder.py)
and the web-layer Golaxy AI level table (katrain/web/platforms/golaxy/engine_client.py).

Rungs 1..39 mirror `GOLAXY_AI_LEVELS` (strongest-first) in reverse (weakest-first);
rung 40 is the v1 ceiling (no Golaxy counterpart) and is intentionally excluded."""

from katrain.core.ladder import LADDER_RUNGS
from katrain.web.platforms.golaxy.engine_client import GOLAXY_AI_LEVELS


def test_ladder_1_39_match_golaxy_levels():
    for rung, gx in zip(LADDER_RUNGS[:39], reversed(GOLAXY_AI_LEVELS)):
        assert (rung.golaxy_level_name, rung.golaxy_api_level, rung.display_elo, rung.ref_rank) == (
            gx["level_name"],
            gx["elo_score"],
            gx["display_elo"],
            gx["ref_rank"],
        )
