#!/usr/bin/env python3
"""Strict serial runner for the rank_1d..rank_6d native HumanSL Golaxy screen."""

from __future__ import annotations

import sys
from pathlib import Path


_BASE_SOURCE = Path(__file__).with_name("run_golaxy_sampling_campaign.py")
_ENTRYPOINT_NAME = __name__
__name__ = "_golaxy_rank1_6_sampling_runner_base"
sys.modules[__name__] = sys.modules[_ENTRYPOINT_NAME]
exec(compile(_BASE_SOURCE.read_bytes(), str(_BASE_SOURCE), "exec"), globals())
__name__ = _ENTRYPOINT_NAME

import golaxy_rank1_6_sampling_campaign as golaxy_rank1_6_sampling_campaign
from katrain.core.ladder import LadderRung
from katrain.web.platforms.golaxy.engine_client import get_level


golaxy_sampling_campaign = golaxy_rank1_6_sampling_campaign


def opponent_for_request(request: golaxy_sampling_campaign.GameRequest) -> LadderRung:
    player_for_request(request)
    row = get_level(request.golaxy_api_level)
    if row is None:
        raise ValueError(f"unknown frozen Golaxy wire level {request.golaxy_api_level}")
    return LadderRung(
        rung=0,
        golaxy_level_name=row["level_name"],
        golaxy_api_level=row["elo_score"],
        display_elo=row["display_elo"],
        ref_rank=row["ref_rank"],
        rank_name=row["level_name"],
        net="golaxy",
        mechanism="net_search",
        human_sl_profile=None,
        max_visits=1,
        human_sl_params={},
    )


if __name__ == "__main__":
    raise SystemExit(main())
