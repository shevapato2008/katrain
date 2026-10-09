"""Pure decisions for the self-owned PvP lobby bot population."""

from random import Random
from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import threading

import pytest

from katrain.core import ladder
from katrain.web.core import pvp_lobby_bots as bots


@pytest.mark.parametrize("fail_at", ["start", "seat"])
def test_failed_bot_room_creation_removes_registered_session_and_shuts_engine(monkeypatch, fail_at):
    from katrain.web import session as session_module

    created = []

    class FailingWebKaTrain:
        def __init__(self, **kwargs):
            self.shutdown_calls = 0
            created.append(self)

        def start(self, **kwargs):
            if fail_at == "start":
                raise RuntimeError("start failed")

        def get_state(self):
            return {}

        def __call__(self, action, **kwargs):
            if fail_at == "seat" and action == "update_player":
                raise RuntimeError("seat setup failed")

        def shutdown(self):
            self.shutdown_calls += 1

    monkeypatch.setattr(session_module, "WebKaTrain", FailingWebKaTrain)
    manager = session_module.SessionManager(enable_engine=False)

    with pytest.raises(RuntimeError):
        manager.create_multiplayer_session(7, -3, b_name="Human", w_name="Bot",
                                           initial_game_type="free", skip_initial_analysis=True)

    assert manager._sessions == {}
    assert len(created) == 1
    assert created[0].shutdown_calls == 1


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


def test_bot_names_look_like_nicknames_and_stay_unique_for_the_lobby_population():
    names = [bots.bot_name(level.rung, slot) for level in bots.playable_rungs() for slot in range(1, 41)]
    assert len(set(names)) == len(names)
    assert all(2 <= len(name) <= 8 for name in names)
    assert all("棋友" not in name and "·" not in name and not any(char.isdigit() for char in name) for name in names)


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


def test_runtime_keeps_idle_reserve_when_human_takes_a_bot():
    runtime = bots.PvpLobbyBotRuntime(None)
    rung = bots.playable_rungs()[0].rung
    runtime.apply_config({"version": 1, "enabled": True, "bot_game_limit": 1,
                          "idle_targets": {str(rung): 2}}, revision=4)
    original = {row["id"] for row in runtime.public_online_rows() if row["ladder_rung"] == rung}
    chosen, generation = runtime.reserve_bot(rung)
    assert chosen in original
    rows = [row for row in runtime.public_online_rows() if row["ladder_rung"] == rung]
    assert len([row for row in rows if row["presence"] == "idle"]) >= 2
    assert next(row for row in rows if row["id"] == chosen)["presence"] == "playing"
    assert runtime.reservation_valid(chosen, generation)
    runtime.release_bot(chosen, generation)
    assert not runtime.reservation_valid(chosen, generation)


def test_bot_pair_rotation_obeys_cap_and_skips_human_waiters():
    runtime = bots.PvpLobbyBotRuntime(None)
    rungs = [level.rung for level in bots.playable_rungs()[:3]]
    runtime.apply_config({"version": 1, "enabled": True, "bot_game_limit": 2,
                          "idle_targets": {}}, revision=1)
    first = runtime.reserve_rotation_pair(human_waiting=False)
    second = runtime.reserve_rotation_pair(human_waiting=False)
    assert first is not None and second is not None
    assert [first[0], second[0]] == rungs[:2]
    assert runtime.reserve_rotation_pair(human_waiting=False) is None
    assert runtime.reserve_rotation_pair(human_waiting=True) is None
    runtime.release_rotation_pair(*first)
    third = runtime.reserve_rotation_pair(human_waiting=False)
    assert third is not None and third[0] == rungs[2]


def test_disabled_config_blocks_new_reservations_but_preserves_active_bot():
    runtime = bots.PvpLobbyBotRuntime(None)
    rung = bots.playable_rungs()[0].rung
    runtime.apply_config({"version": 1, "enabled": True, "bot_game_limit": 1,
                          "idle_targets": {}}, revision=1)
    chosen, generation = runtime.reserve_bot(rung)
    runtime.apply_config({"version": 1, "enabled": False, "bot_game_limit": 0,
                          "idle_targets": {}}, revision=2)
    assert runtime.reserve_bot(rung) is None
    assert runtime.reservation_valid(chosen, generation)
    assert any(row["id"] == chosen for row in runtime.public_online_rows())


def test_ladder_candidate_does_not_commit_its_move(monkeypatch):
    from katrain.core import ai

    node = object()
    move = object()
    class FakeGame:
        current_node = node
        def play(self, _move):
            raise AssertionError("generation must not commit")
    monkeypatch.setattr(ai.LadderStrategy, "generate_move", lambda self: (move, "certified"))
    assert ai.generate_ladder_candidate(FakeGame(), 1) == (node, move, "certified")


@pytest.mark.asyncio
async def test_bot_second_pass_is_scored_before_terminal_finish():
    runtime = bots.PvpLobbyBotRuntime(None)
    node = SimpleNamespace()
    game = SimpleNamespace(current_node=node)
    committed = []
    katrain = SimpleNamespace(game=game, ensure_current_score=lambda **kwargs: -1.5,
                             _commit_end_state=lambda result, **kwargs: committed.append((result, kwargs)),
                             get_state=lambda: {"end_result": "W+1.5"}, update_state=lambda: None)
    session = SimpleNamespace(session_id="two-pass", lock=threading.Lock(), end_game_lock=asyncio.Lock(),
                              katrain=katrain, game_ended=True, bot_finalized=False)
    runtime._sessions[session.session_id] = ()
    runtime.finish = AsyncMock()

    await runtime.finish_terminal(session, SimpleNamespace(game=game, node=node, result="B+9.5?"))

    assert committed == [("W+1.5", {"node": node, "fill_pending": True})]
    runtime.finish.assert_awaited_once_with(session, reason="two_pass", result="W+1.5")


@pytest.mark.asyncio
async def test_invalid_engine_score_degrades_instead_of_fabricating_result():
    runtime = bots.PvpLobbyBotRuntime(None)
    node = SimpleNamespace()
    game = SimpleNamespace(current_node=node)
    katrain = SimpleNamespace(game=game, ensure_current_score=lambda **kwargs: float("nan"), update_state=lambda: None)
    session = SimpleNamespace(session_id="stalled", lock=threading.Lock(), end_game_lock=asyncio.Lock(),
                              katrain=katrain, game_ended=True, bot_finalized=False)
    runtime._sessions[session.session_id] = ()
    runtime.finish = AsyncMock()
    runtime._abort_stalled = AsyncMock()

    await runtime.finish_terminal(session, SimpleNamespace(game=game, node=node, result="board-game-end"))

    assert session.bot_degraded is True
    assert runtime.engine_errors == 1
    runtime.finish.assert_not_awaited()
    runtime._stall_tasks["stalled"].cancel()


@pytest.mark.parametrize("invalidate", ["delete", "cancel"])
def test_generated_candidate_cannot_commit_after_session_or_reservation_invalidated(invalidate):
    rung = bots.playable_rungs()[0].rung
    state = SimpleNamespace()
    runtime = bots.PvpLobbyBotRuntime(SimpleNamespace(state=state))
    runtime.apply_config({"version": 1, "enabled": True, "bot_game_limit": 0,
                          "idle_targets": {}}, revision=1)
    identity, generation = runtime.reserve_bot(rung)
    node = SimpleNamespace(next_player="B")
    played = []
    game = SimpleNamespace(current_node=node, end_result=None,
                           play=lambda move, **kwargs: played.append(move))
    katrain = SimpleNamespace(game=game, ai_ladder_commit_lock=threading.RLock(),
                             get_state=lambda: {}, update_state=lambda: None)
    session = SimpleNamespace(session_id="game-1", player_b_id=identity, player_w_id=1,
                              game_ended=False, lock=threading.Lock(), katrain=katrain)
    state.session_manager = SimpleNamespace(_lock=threading.Lock(), _sessions={session.session_id: session})
    if invalidate == "delete":
        state.session_manager._sessions.clear()
    else:
        runtime.release_bot(identity, generation)

    assert runtime.commit_candidate(session, identity, generation, (node, object(), "certified")) is False
    assert played == []
