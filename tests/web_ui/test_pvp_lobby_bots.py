"""Pure decisions for the self-owned PvP lobby bot population."""

from random import Random
from types import SimpleNamespace

import pytest

from katrain.core import ladder
from katrain.web.core import pvp_lobby_bots as bots


def test_playable_catalog_uses_only_fitted_certified_available_levels(monkeypatch):
    levels = (
        SimpleNamespace(
            rung=1, rank_name="20级", recipe=object(), certification_status="certified", availability="available"
        ),
        SimpleNamespace(
            rung=2, rank_name="19级", recipe=None, certification_status="certified", availability="available"
        ),
        SimpleNamespace(
            rung=3, rank_name="18级", recipe=object(), certification_status="provisional", availability="available"
        ),
        SimpleNamespace(
            rung=4, rank_name="17级", recipe=object(), certification_status="certified", availability="unavailable"
        ),
    )
    monkeypatch.setattr(ladder, "LADDER_LEVELS", levels)

    assert [(level.rung, level.rank_label) for level in bots.playable_rungs()] == [(1, "20级")]


def test_real_playable_catalog_has_29_rungs_with_canonical_names():
    levels = bots.playable_rungs()
    assert len(levels) == 29
    assert [(level.rung, level.rank_label) for level in levels] == [
        (level.rung, level.rank_name)
        for level in ladder.LADDER_LEVELS
        if level.recipe is not None and level.certification_status == "certified" and level.availability == "available"
    ]


def test_bot_ids_are_negative_and_names_are_unique_across_rungs_and_slots():
    seats = [(rung, slot) for rung in (1, 20, 41) for slot in (1, 2, 1001)]
    ids = [bots.bot_id(rung, slot) for rung, slot in seats]
    names = [bots.bot_name(rung, slot) for rung, slot in seats]

    assert all(value < 0 for value in ids)
    assert len(set(ids)) == len(ids)
    assert len(set(names)) == len(names)
    assert bots.bot_id(1, 1) == bots.bot_id(1, 1)
    assert bots.bot_name(1, 1) == bots.bot_name(1, 1)
    assert all("bot" not in name.lower() and "机器人" not in name for name in names)


@pytest.mark.parametrize("rung,slot", [(0, 1), (1, 0), (True, 1), (1, False)])
def test_bot_identity_rejects_nonpositive_or_noninteger_coordinates(rung, slot):
    with pytest.raises(ValueError):
        bots.bot_id(rung, slot)
    with pytest.raises(ValueError):
        bots.bot_name(rung, slot)


def test_config_defaults_omitted_playable_rungs_to_two_without_mutating_input():
    supplied = {"version": 1, "enabled": False, "bot_game_limit": 3, "idle_targets": {"1": 4}}
    normalized = bots.validate_config(supplied)

    assert normalized["enabled"] is False
    assert normalized["bot_game_limit"] == 3
    assert normalized["idle_targets"] == {
        str(level.rung): (4 if level.rung == 1 else 2) for level in bots.playable_rungs()
    }
    assert supplied["idle_targets"] == {"1": 4}


@pytest.mark.parametrize(
    "change",
    [
        {"version": 2},
        {"enabled": 1},
        {"bot_game_limit": -1},
        {"bot_game_limit": 7},
        {"bot_game_limit": True},
        {"idle_targets": {"1": 0}},
        {"idle_targets": {"1": 21}},
        {"idle_targets": {"1": True}},
        {"idle_targets": {"999": 2}},
        {"idle_targets": {1: 2}},
        {"unexpected": 1},
    ],
)
def test_config_rejects_values_outside_frozen_contract(change):
    config = {"version": 1, "enabled": False, "bot_game_limit": 3, "idle_targets": {}}
    config.update(change)
    with pytest.raises(ValueError):
        bots.validate_config(config)


def test_idle_reserve_deficit_is_rank_local_and_excludes_busy_bots():
    config = bots.validate_config(
        {"version": 1, "enabled": True, "bot_game_limit": 3, "idle_targets": {"1": 3, "4": 1}}
    )
    deficits = bots.idle_reserve_deficit(config, {1: 1, 4: 2})

    assert deficits[1] == 2
    assert deficits[4] == 0
    assert deficits[7] == 2  # absent count never borrows an idle bot from another rung


def test_rotation_selects_next_eligible_rung_and_wraps():
    assert bots.choose_next_rung([7, 1, 4], after_rung=None) == 1
    assert bots.choose_next_rung([7, 1, 4], after_rung=1) == 4
    assert bots.choose_next_rung([7, 1, 4], after_rung=4) == 7
    assert bots.choose_next_rung([7, 1, 4], after_rung=7) == 1
    assert bots.choose_next_rung([], after_rung=7) is None


@pytest.mark.parametrize("eligible", [[1, True], [1, "4"]])
def test_rotation_rejects_invalid_raw_rungs_before_deduplication_or_sorting(eligible):
    with pytest.raises(ValueError, match="unplayable rung"):
        bots.choose_next_rung(eligible)


def test_each_move_delay_is_selected_inside_five_to_thirty_seconds():
    class BoundaryRng:
        def __init__(self):
            self.bounds = []

        def randint(self, start, stop):
            self.bounds.append((start, stop))
            return start if len(self.bounds) == 1 else stop

    rng = BoundaryRng()
    assert bots.next_move_delay(rng) == 5
    assert bots.next_move_delay(rng) == 30
    assert rng.bounds == [(5, 30), (5, 30)]
    assert all(5 <= bots.next_move_delay(Random(seed)) <= 30 for seed in range(20))
