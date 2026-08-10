"""Where a counted result moves a player on the 41-rung ladder.

Ten of the 41 rungs (准1段–准9段 and 职业顶尖) have no fitted strength recipe, so no
opponent can ever be built for them. The settlement rule therefore cannot be plain
arithmetic on the rung number: 5段 is rung 30 and 准6段 is rung 31, so `rung + 1`
promotes a 5段 player onto a rung they can never play from.

These tests exist because that is not observable today — `_CERTIFIED_RUNGS` is empty,
so every game settles as `counted=0` and this code path never runs against a real
user. No device run will catch a regression here; only these assertions will.
"""

import pytest

from katrain.core import ladder
from katrain.web.core import models_db
from katrain.web.core.ai_ladder_ranked import PLACEMENT_GAMES, AiLadderRankedRepository

# Derived, not hardcoded: all 41 rungs now ship a recipe, so this is empty. Keeping it
# computed means the guard below stays meaningful if a rung ever loses its recipe again.
RECIPELESS = tuple(l.rung for l in ladder.LADDER_LEVELS if l.recipe is None)


def profile(**overrides):
    p = models_db.AiLadderProfile(
        user_id=1,
        ai_ladder_rung=None,
        placement_lo=1,
        placement_hi=32,
        placement_completed=0,
        net_score=0,
    )
    for key, value in overrides.items():
        setattr(p, key, value)
    return p


def apply(p, *results):
    for result in results:
        AiLadderRankedRepository._apply_result(p, result)
    return p


# --- promotion / demotion ---------------------------------------------------


def test_three_net_wins_promote_one_playable_rung_and_reset_the_score():
    p = apply(profile(ai_ladder_rung=30, net_score=0), "win", "win", "win")
    assert p.ai_ladder_rung == 31  # 准6段 -- one rung, not a jump over it
    assert ladder.get_level(p.ai_ladder_rung).rank_name == "准6段"
    assert p.net_score == 0


def test_three_net_losses_demote_one_playable_rung():
    p = apply(profile(ai_ladder_rung=30, net_score=0), "loss", "loss", "loss")
    assert p.ai_ladder_rung == 29  # 准5段
    assert p.net_score == 0


def test_two_net_wins_move_nothing():
    p = apply(profile(ai_ladder_rung=30, net_score=0), "win", "win")
    assert p.ai_ladder_rung == 30
    assert p.net_score == 2


def test_a_loss_cancels_a_win_rather_than_counting_the_last_five():
    p = apply(profile(ai_ladder_rung=30, net_score=0), "win", "win", "loss", "win", "win")
    assert p.ai_ladder_rung == 31
    assert p.net_score == 0


def test_no_sequence_of_results_can_park_a_player_on_a_recipeless_rung():
    for start in ladder.PLAYABLE_RUNGS:
        for run in ("win", "loss"):
            p = profile(ai_ladder_rung=start, net_score=0)
            for _ in range(30):
                apply(p, run)
                assert p.ai_ladder_rung not in RECIPELESS, (start, run, p.ai_ladder_rung)


def test_promotion_saturates_at_the_top_playable_rung():
    top = ladder.PLAYABLE_RUNGS[-1]
    p = profile(ai_ladder_rung=top, net_score=0)
    for _ in range(12):
        apply(p, "win")
    assert p.ai_ladder_rung == top


def test_demotion_saturates_at_the_bottom_playable_rung():
    bottom = ladder.PLAYABLE_RUNGS[0]
    p = profile(ai_ladder_rung=bottom, net_score=0)
    for _ in range(12):
        apply(p, "loss")
    assert p.ai_ladder_rung == bottom


# --- placement --------------------------------------------------------------


def test_placement_grants_no_rung_before_the_fifth_game():
    p = profile()
    for _ in range(PLACEMENT_GAMES - 1):
        apply(p, "win")
        assert p.ai_ladder_rung is None
    apply(p, "win")
    assert p.ai_ladder_rung is not None


def test_placement_narrows_towards_the_winning_half():
    p = apply(profile(), "win")
    assert (p.placement_lo, p.placement_hi) == (17, 32)
    p = apply(profile(), "loss")
    assert (p.placement_lo, p.placement_hi) == (1, 16)


@pytest.mark.parametrize("path", [tuple(bits) for bits in __import__("itertools").product(("win", "loss"), repeat=5)])
def test_every_placement_path_lands_on_a_playable_rung(path):
    p = apply(profile(), *path)
    assert p.placement_completed == PLACEMENT_GAMES
    assert p.ai_ladder_rung in ladder.PLAYABLE_RUNGS, (path, p.ai_ladder_rung)
    assert ladder.get_level(p.ai_ladder_rung).recipe is not None
    assert p.net_score == 0


# --- the opponent a player is seated against --------------------------------


def test_the_seated_opponent_is_still_the_raw_midpoint():
    """The placement search still names the raw midpoint, and that is now always seatable.

    This used to be an open question: 6 of the 31 distinct search windows reachable from the
    default 1..32 range named a recipe-less rung as the opponent, so those placement games
    could not be seated at all. Filling all 41 recipes closed it without touching the search
    itself -- the midpoint rule is unchanged, every midpoint is simply playable now.
    """
    from katrain.web.core.ai_ladder_ranked import expected_opponent_rung

    unseatable = 0
    frontier = {(1, 32)}
    for _ in range(PLACEMENT_GAMES):
        nxt = set()
        for lo, hi in frontier:
            mid = (lo + hi) // 2
            assert expected_opponent_rung(None, lo, hi) == mid
            if mid not in ladder.PLAYABLE_RUNGS:
                unseatable += 1
            nxt.add((mid + 1, hi))
            nxt.add((lo, mid))
        frontier = nxt
    assert unseatable == 0


def test_a_placed_player_faces_their_own_rung():
    from katrain.web.core.ai_ladder_ranked import expected_opponent_rung

    for rung in ladder.PLAYABLE_RUNGS:
        assert expected_opponent_rung(rung, 1, 32) == rung


def test_the_status_endpoint_uses_the_same_opponent_rule_as_settlement():
    """They used to inline the same formula twice, once in the endpoint and once in the
    settlement check. When two copies drift, a legitimately seated game settles as
    `opponent_rung_mismatch` and the player silently stops earning rank."""
    from katrain.web.api.v1.endpoints import ai_ladder as endpoint
    from katrain.web.core import ai_ladder_ranked

    assert endpoint.expected_opponent_rung is ai_ladder_ranked.expected_opponent_rung
