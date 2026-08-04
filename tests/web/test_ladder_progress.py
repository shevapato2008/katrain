"""Placement/promotion rules and the playable-rung mapping for rated play.

These assert product behaviour a user would notice if it broke: that placement
always resolves, where it can land you, that promotion needs a net +3 rather than
a bare majority, and -- the one that forced the position-space design -- that no
opponent or landing spot is ever a rung with no strength recipe.
"""

import itertools

import pytest

from katrain.core.ladder import LADDER_LEVELS, get_level
from katrain.web.core.ladder_catalog import (
    legacy_rank_to_position,
    playable_rungs,
    position_count,
    position_of,
    rung_at,
)
from katrain.web.core.ladder_progress import (
    NET_WIN_THRESHOLD,
    PLACEMENT_GAMES,
    PLACEMENT_WINDOW,
    apply_ladder_result,
    placement_apply,
    placement_opponent,
    placement_settled,
    seed_placement_window,
)

# --- the playable ladder -----------------------------------------------------


def test_playable_rungs_are_exactly_the_ones_with_a_recipe():
    assert playable_rungs() == tuple(lv.rung for lv in LADDER_LEVELS if lv.recipe is not None)


def test_every_playable_rung_round_trips_through_position_space():
    for pos in range(1, position_count() + 1):
        assert position_of(rung_at(pos)) == pos


def test_playable_rungs_are_strictly_increasing_in_strength():
    rungs = playable_rungs()
    assert list(rungs) == sorted(rungs)


def test_a_rung_without_a_recipe_has_no_position():
    holes = [lv.rung for lv in LADDER_LEVELS if lv.recipe is None]
    assert holes, "this test is meaningless once every rung is fitted"
    for rung in holes:
        with pytest.raises(ValueError, match="no strength recipe"):
            position_of(rung)


@pytest.mark.parametrize(
    "legacy,expected_rung",
    [("20k", 1), ("1k", 20), ("1d", 22), ("2d", 24), ("9d", 38), ("12d", 38)],
)
def test_legacy_rank_seeds_from_the_matching_rung(legacy, expected_rung):
    assert rung_at(legacy_rank_to_position(legacy)) == expected_rung


@pytest.mark.parametrize("legacy", [None, "", "garbage", "0k", "21k", "0d"])
def test_unusable_legacy_ranks_give_no_seed(legacy):
    assert legacy_rank_to_position(legacy) is None


# --- placement ---------------------------------------------------------------


def test_no_legacy_rank_starts_at_the_bottom_window():
    assert seed_placement_window(None, position_count()) == (1, PLACEMENT_WINDOW)


def test_window_is_always_a_power_of_two_wide():
    """Width 32 on every branch is what makes placement take exactly 5 games."""
    n = position_count()
    for legacy in [None, "20k", "10k", "1k", "1d", "5d", "9d", "12d"]:
        lo, hi = seed_placement_window(legacy_rank_to_position(legacy), n)
        assert lo >= 1
        assert hi - lo + 1 == PLACEMENT_WINDOW


def test_the_window_always_covers_the_top_of_the_ladder_for_a_strong_seed():
    n = position_count()
    lo, hi = seed_placement_window(legacy_rank_to_position("9d"), n)
    assert min(hi, n) == n


def test_five_games_always_resolve_a_position():
    """2**5 == 32, so every win/loss sequence must collapse the window exactly."""
    n = position_count()
    lo0, hi0 = seed_placement_window(None, n)
    landed = set()
    for outcomes in itertools.product([True, False], repeat=PLACEMENT_GAMES):
        lo, hi = lo0, hi0
        for i, won in enumerate(outcomes):
            assert placement_settled(lo, hi, n) is None, f"settled after {i} games"
            lo, hi = placement_apply(lo, hi, won)
        settled = placement_settled(lo, hi, n)
        assert settled is not None, f"{outcomes} left the window at {lo}..{hi}"
        landed.add(settled)
    assert landed == set(range(lo0, min(hi0, n) + 1))


def test_placement_never_seats_an_opponent_without_a_recipe():
    """The reason placement runs in position space at all."""
    n = position_count()
    for legacy in [None, "10k", "1d", "5d", "9d"]:
        lo0, hi0 = seed_placement_window(legacy_rank_to_position(legacy), n)
        for outcomes in itertools.product([True, False], repeat=PLACEMENT_GAMES):
            lo, hi = lo0, hi0
            for won in outcomes:
                rung = rung_at(placement_opponent(lo, hi, n))
                assert get_level(rung).recipe is not None
                lo, hi = placement_apply(lo, hi, won)
            assert get_level(rung_at(placement_settled(lo, hi, n))).recipe is not None


def test_placement_opponent_rejects_an_inverted_window():
    with pytest.raises(ValueError):
        placement_opponent(20, 19, position_count())


def test_short_ladder_still_places_in_exactly_five_games():
    """Search slots above the ladder clamp onto its top rather than overshooting."""
    n = 6
    lo, hi = seed_placement_window(None, n)
    assert (lo, hi) == (1, PLACEMENT_WINDOW)
    for _ in range(PLACEMENT_GAMES):
        assert 1 <= placement_opponent(lo, hi, n) <= n
        lo, hi = placement_apply(lo, hi, won=True)
    assert placement_settled(lo, hi, n) == n


# --- promotion ---------------------------------------------------------------


def test_three_net_wins_promote_and_reset():
    n = position_count()
    pos, net = 10, 0
    for _ in range(NET_WIN_THRESHOLD):
        pos, net = apply_ladder_result(pos, net, True, n)
    assert (pos, net) == (11, 0)


def test_three_net_losses_demote_and_reset():
    n = position_count()
    pos, net = 10, 0
    for _ in range(NET_WIN_THRESHOLD):
        pos, net = apply_ladder_result(pos, net, False, n)
    assert (pos, net) == (9, 0)


def test_three_wins_and_two_losses_do_not_promote():
    """The recent-form strip shows 3W2L; the ledger must still read net +1."""
    n = position_count()
    pos, net = 10, 0
    for won in [True, False, True, True, False]:
        pos, net = apply_ladder_result(pos, net, won, n)
    assert (pos, net) == (10, 1)


def test_positions_saturate_at_both_ends():
    n = position_count()
    top, net = n, 0
    for _ in range(NET_WIN_THRESHOLD):
        top, net = apply_ladder_result(top, net, True, n)
    assert (top, net) == (n, 0)

    bottom, net = 1, 0
    for _ in range(NET_WIN_THRESHOLD):
        bottom, net = apply_ladder_result(bottom, net, False, n)
    assert (bottom, net) == (1, 0)


def test_promotion_never_lands_on_a_rung_without_a_recipe():
    n = position_count()
    for pos in range(1, n + 1):
        for won in (True, False):
            new_pos, _ = apply_ladder_result(pos, 2 if won else -2, won, n)
            assert get_level(rung_at(new_pos)).recipe is not None


def test_result_rejects_a_position_outside_the_ladder():
    with pytest.raises(ValueError):
        apply_ladder_result(position_count() + 1, 0, True, position_count())
