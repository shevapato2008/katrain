import pytest

from smartbox_xiangqi_ranked.scoring import (
    ANCHORS,
    FARM_CEIL,
    INITIAL_RATING,
    K_PROVISIONAL,
    K_STABLE,
    PROVISIONAL_GAMES,
    RATING_FLOOR,
    SCORING_CONTRACT_VERSION,
    SUPPORTED_CONTRACTS,
    RatingState,
    apply_one,
    apply_one_v4,
    outcome_from_result,
    pick_level,
    project_three,
)


@pytest.mark.parametrize(
    "outcome,expected_hex,display_delta",
    [
        ("win", "0x1.037ef1e602bd6p+10", 38),
        ("draw", "0x1.fcfde3cc057abp+9", 18),
        ("loss", "0x1.f2fde3cc057abp+9", -2),
    ],
)
def test_v4_keeps_exact_continuous_rating_and_separate_display_delta(outcome, expected_hex, display_delta):
    change = apply_one_v4(RatingState(INITIAL_RATING, 0), opponent_level=3, outcome=outcome)

    assert change.after.rating.hex() == expected_hex
    assert change.after.rated_games == 1
    assert change.display_delta == display_delta
    assert change.display_after - change.display_before == display_delta


def test_v4_switches_k_factor_only_after_twenty_counted_games():
    before = apply_one_v4(RatingState(1000.0, PROVISIONAL_GAMES - 1), opponent_level=3, outcome="win")
    after = apply_one_v4(RatingState(1000.0, PROVISIONAL_GAMES), opponent_level=3, outcome="win")

    assert K_PROVISIONAL == 40 and before.after.rating.hex() == "0x1.037ef1e602bd6p+10"
    assert K_STABLE == 20 and after.after.rating.hex() == "0x1.fd7ef1e602bd6p+9"


def test_v4_enforces_floor_and_win_hard_ceiling_without_lowering_a_winner():
    floored = apply_one_v4(RatingState(100.0, 100), opponent_level=9, outcome="loss")
    capped = apply_one_v4(RatingState(FARM_CEIL[1] - 0.1, 100), opponent_level=1, outcome="win")
    already_above = apply_one_v4(RatingState(1800.0, 100), opponent_level=1, outcome="win")

    assert floored.after.rating == RATING_FLOOR == 100
    assert capped.after.rating == FARM_CEIL[1] == ANCHORS[1] + 130
    assert already_above.after.rating == 1800.0


@pytest.mark.parametrize(
    "result,color,outcome",
    [
        ("1-0", "red", "win"),
        ("1-0", "black", "loss"),
        ("0-1", "red", "loss"),
        ("0-1", "black", "win"),
        ("1/2-1/2", "red", "draw"),
        ("1/2-1/2", "black", "draw"),
    ],
)
def test_result_mapping_is_from_the_players_red_or_black_point_of_view(result, color, outcome):
    assert outcome_from_result(result, color) == outcome


@pytest.mark.parametrize("time_control", ["unlimited", "blitz5", "standard10", "slow20"])
def test_time_control_is_frozen_context_but_never_changes_v4_math(time_control):
    baseline = apply_one_v4(RatingState(1377.25, 7), opponent_level=5, outcome="draw")
    actual = apply_one(
        RatingState(1377.25, 7),
        opponent_level=5,
        outcome="draw",
        time_control=time_control,
        contract_version=4,
    )
    assert actual == baseline


def test_project_three_is_exactly_three_independent_apply_one_calls():
    state = RatingState(1421.125, 19)
    projected = project_three(state, opponent_level=4, time_control="slow20")

    assert projected == {
        outcome: apply_one(
            state,
            opponent_level=4,
            outcome=outcome,
            time_control="slow20",
            contract_version=4,
        )
        for outcome in ("win", "draw", "loss")
    }


def test_contract_registry_is_append_only_and_routes_active_v4():
    assert SCORING_CONTRACT_VERSION == 4
    assert SUPPORTED_CONTRACTS[4] is apply_one_v4


@pytest.mark.parametrize(
    "mapping,key,value",
    [
        (ANCHORS, 1, 9999),
        (FARM_CEIL, 1, 9999),
        (SUPPORTED_CONTRACTS, 4, lambda *_args, **_kwargs: None),
    ],
)
def test_public_scoring_registries_are_deeply_immutable(mapping, key, value):
    before = dict(mapping)
    try:
        with pytest.raises(TypeError):
            mapping[key] = value
    finally:
        if isinstance(mapping, dict):
            mapping.clear()
            mapping.update(before)


def test_registry_immutability_keeps_the_frozen_v4_output_unchanged():
    assert (
        apply_one_v4(RatingState(1377.25, 7), opponent_level=5, outcome="draw").after.rating.hex()
        == "0x1.5cf99c843bf9bp+10"
    )


def test_pick_level_is_monotone_and_every_catalog_level_is_reachable():
    picked = [pick_level(float(rating)) for rating in range(RATING_FLOOR, 3401)]
    assert picked == sorted(picked)
    assert set(picked) == set(range(1, 10))


@pytest.mark.parametrize("bad", ["WIN", "aborted", 1, None])
def test_unvalidated_outcomes_are_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        apply_one_v4(RatingState(1000.0, 0), opponent_level=3, outcome=bad)
