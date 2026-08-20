"""Where a counted result moves a player on the 41-rung ladder.

12 of the 41 rungs are RETIRED (`ladder._RETIRED_RUNGS`): they keep their catalog position
and their recipe -- so a rung number stored in the immutable ledger stays interpretable --
but no player may be seated on them. The settlement rule therefore cannot be plain
arithmetic on the rung number: 5段 is rung 30 and the retired 准6段 is rung 31, so `rung + 1`
promotes a 5段 player onto a rung no opponent will be built for.

These tests exist because that is not observable today — `_CERTIFIED_RUNGS` is empty,
so every game settles as `counted=0` and this code path never runs against a real
user. No device run will catch a regression here; only these assertions will.
"""

import pytest

from katrain.core import ladder
from katrain.web.core import models_db
from katrain.web.core.ai_ladder_ranked import PLACEMENT_GAMES, AiLadderRankedRepository

# Derived, not hardcoded: all 41 rungs still ship a recipe, so this is empty -- retirement
# is not recipe removal. Keeping it computed means the guard stays meaningful either way.
RECIPELESS = tuple(l.rung for l in ladder.LADDER_LEVELS if l.recipe is None)
UNSEATABLE = tuple(l.rung for l in ladder.LADDER_LEVELS if l.rung not in ladder.PLAYABLE_RUNGS)


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
    # 准6段(31) is retired, so one playable step from 5段 is 6段(32) -- the step skips it.
    assert p.ai_ladder_rung == 32
    assert ladder.get_level(p.ai_ladder_rung).rank_name == "6段"
    assert p.net_score == 0


def test_three_net_losses_demote_one_playable_rung():
    p = apply(profile(ai_ladder_rung=30, net_score=0), "loss", "loss", "loss")
    assert p.ai_ladder_rung == 28  # 4段 -- 准5段(29) is retired
    assert p.net_score == 0


def test_two_net_wins_move_nothing():
    p = apply(profile(ai_ladder_rung=30, net_score=0), "win", "win")
    assert p.ai_ladder_rung == 30
    assert p.net_score == 2


def test_a_loss_cancels_a_win_rather_than_counting_the_last_five():
    p = apply(profile(ai_ladder_rung=30, net_score=0), "win", "win", "loss", "win", "win")
    assert p.ai_ladder_rung == 32
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


def test_every_reachable_placement_window_seats_a_playable_rung():
    """The gate that had to land together with retirement.

    The placement search walks RAW rung numbers, so its midpoint can name a retired rung --
    16 (5级) is the very first one, the midpoint of the default 1..32 window. Before the
    snap, that game could not be seated at all. `expected_opponent_rung` now snaps, and
    this walks every window reachable in 5 games from every legal starting window to prove
    there is no hole left.

    Mutation check (2026-08-20): dropping the snap from `expected_opponent_rung` makes this
    fail with 12 unseatable windows out of the 31 reachable from 1..32 alone (measured).
    """
    from katrain.web.core.ai_ladder_ranked import expected_opponent_rung, initial_placement_window

    starts = {initial_placement_window(rank) for rank in (None, "20k", "10k", "1k", "1d", "5d", "9d")}
    checked = 0
    for start in starts:
        frontier = {start}
        for _ in range(PLACEMENT_GAMES):
            nxt = set()
            for lo, hi in frontier:
                seated = expected_opponent_rung(None, lo, hi)
                assert seated in ladder.PLAYABLE_RUNGS, (lo, hi, seated)
                assert ladder.get_level(seated).recipe is not None
                checked += 1
                pivot = (lo + hi) // 2  # the search cursor stays raw -- see _apply_result
                nxt.add((pivot + 1, hi))
                nxt.add((lo, pivot))
            frontier = nxt
    assert checked >= 31, checked


def test_the_placement_cursor_stays_raw_so_the_window_never_inverts():
    """Snapping the OPPONENT is required; snapping the search cursor would be a bug.

    `placement_lo <= placement_hi` has to hold after every result, including on windows too
    narrow to contain any playable rung. That is why `_apply_result` splits on the raw
    midpoint while the opponent comes from `expected_opponent_rung`.
    """
    import itertools

    for path in itertools.product(("win", "loss"), repeat=PLACEMENT_GAMES):
        p = profile()
        for result in path:
            apply(p, result)
            assert p.placement_lo <= p.placement_hi, (path, p.placement_lo, p.placement_hi)
        assert p.ai_ladder_rung in ladder.PLAYABLE_RUNGS


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
