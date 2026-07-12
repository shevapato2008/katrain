"""Poller-level tests for `_handle_confirmed_move` (Task 7, review B5/M1/M4/m2).

Extracted from `_vision_move_poller` (server.py) specifically so this per-move
handling — turn-check, gateway dispatch, and the bounded engine-move recovery
state machine — can be driven directly with a mocked gateway/vision/tracker,
without running the actual infinite poll loop.
"""

import asyncio
import logging
import threading
from types import SimpleNamespace

import pytest

from katrain.vision.ipc import ConfirmedMove
from katrain.web.core.engine_recovery import EngineRecoveryConfig, EngineRecoveryTracker
from katrain.web.platforms.gateway import PlatformMoveRejectedError
from katrain.web.server import _handle_confirmed_move

BLACK, WHITE = 1, 2
log = logging.getLogger("test_vision_move_poller")


class FakeKatrain:
    def __init__(self, player_to_move="B"):
        self.plays = []
        self._state = {"stones": [], "board_size": [19, 19], "player_to_move": player_to_move}

    def get_state(self):
        return self._state

    def __call__(self, command, coords=None, **kwargs):
        if command == "play":
            self.plays.append(coords)


class FakeSession:
    def __init__(self, player_to_move="B"):
        self.katrain = FakeKatrain(player_to_move)
        self.last_state = {"player_to_move": player_to_move}
        self.lock = threading.Lock()


class FakeSessionManager:
    def __init__(self, sessions=None):
        self.sessions = sessions or {}
        self.broadcasts = []

    def get_session(self, session_id):
        if session_id not in self.sessions:
            raise KeyError(session_id)
        return self.sessions[session_id]

    def broadcast_to_session(self, session_id, payload):
        self.broadcasts.append((session_id, payload))


class FakeVision:
    def __init__(self):
        self.expected_pushes = []

    def set_expected_from_stones(self, stones, board_size=19):
        self.expected_pushes.append(stones)


class FakeGateway:
    """is_platform_game=True by default; `outcomes` is a queue of either a plain
    value (success) or an Exception instance to raise, consumed FIFO across
    successive play_move calls."""

    def __init__(self, game_id="g1", outcomes=None, is_platform=True):
        self._game_id = game_id
        self._outcomes = list(outcomes or [])
        self.is_platform = is_platform
        self.calls = []

    def is_platform_game(self, session_id):
        return self.is_platform

    def get_game_id(self, session_id):
        return self._game_id

    async def play_move(self, session_id, col, row, user_id=0):
        self.calls.append((session_id, col, row))
        outcome = self._outcomes.pop(0) if self._outcomes else "ok"
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeOrchestrator:
    def __init__(self):
        self.entered = []
        self.cleared = 0

    def enter_engine_error(self, coords, token):
        self.entered.append((coords, token))

    def clear_engine_error(self):
        self.cleared += 1


def _app(session_manager, gateway=None, tracker=None, orchestrator="unset"):
    state = SimpleNamespace(session_manager=session_manager)
    if gateway is not None:
        state.platform_gateway = gateway
    if tracker is not None:
        state.engine_recovery = tracker
    if orchestrator != "unset":
        state.physical_play = orchestrator
    return SimpleNamespace(state=state)


def _move(col=3, row=3, color=BLACK):
    return ConfirmedMove(col=col, row=row, color=color)


class TestOutOfTurnAndSessionMissing:
    def test_out_of_turn_move_ignored_rearms_with_throttle(self):
        sm = FakeSessionManager({"s1": FakeSession(player_to_move="W")})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(color=BLACK), log))

        assert delay == 0.5
        assert gateway.calls == []  # never reached the tunnel
        assert vision.expected_pushes  # re-armed

    def test_session_missing_clears_tracker_and_returns_no_delay(self):
        sm = FakeSessionManager({})  # "s1" not present -> get_session raises KeyError
        tracker = EngineRecoveryTracker()
        tracker.on_failure(game_id="g1", coords=(3, 3), reason="engine_error")
        app = _app(sm, gateway=FakeGateway(), tracker=tracker)
        vision = FakeVision()

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(), log))

        assert delay == 0.0
        assert tracker.active_episode is None


class TestLocalNonPlatformGame:
    def test_local_game_plays_directly_no_gateway_recovery_involved(self):
        sm = FakeSessionManager({"s1": FakeSession()})
        gateway = FakeGateway(is_platform=False)
        app = _app(sm, gateway=gateway)
        vision = FakeVision()

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(), log))

        assert delay == 0.0
        assert gateway.calls == []
        assert sm.sessions["s1"].katrain.plays  # played locally
        assert vision.expected_pushes  # orchestrator absent -> fallback rearm


class TestCountedReasonsThreshold:
    def test_engine_error_below_threshold_rearms_with_throttle(self):
        sm = FakeSessionManager({"s1": FakeSession()})
        gateway = FakeGateway(outcomes=[PlatformMoveRejectedError("boom", reason="engine_error")])
        tracker = EngineRecoveryTracker(EngineRecoveryConfig(engine_move_max_attempts=3))
        app = _app(sm, gateway=gateway, tracker=tracker)
        vision = FakeVision()

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(), log))

        assert delay == 0.5
        assert tracker.active_episode.count == 1
        assert vision.expected_pushes  # re-armed
        assert sm.broadcasts == []  # no dialog yet

    def test_threshold_stops_rearm_enters_orchestrator_and_broadcasts(self):
        sm = FakeSessionManager({"s1": FakeSession()})
        gateway = FakeGateway(
            outcomes=[
                PlatformMoveRejectedError("e1", reason="engine_error"),
                PlatformMoveRejectedError("e2", reason="engine_error"),
                PlatformMoveRejectedError("e3", reason="engine_error"),
            ]
        )
        tracker = EngineRecoveryTracker(EngineRecoveryConfig(engine_move_max_attempts=3))
        orchestrator = FakeOrchestrator()
        app = _app(sm, gateway=gateway, tracker=tracker, orchestrator=orchestrator)
        vision = FakeVision()

        d1 = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(), log))
        d2 = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(), log))
        d3 = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(), log))

        assert (d1, d2) == (0.5, 0.5)
        assert d3 == 0.0  # STOP re-arming at threshold
        pushes_before_trip = len(vision.expected_pushes)
        assert pushes_before_trip == 2  # only the first two re-armed

        assert len(orchestrator.entered) == 1
        coords, token = orchestrator.entered[0]
        assert isinstance(token, str) and token

        assert len(sm.broadcasts) == 1
        sid, payload = sm.broadcasts[0]
        assert sid == "s1"
        assert payload["type"] == "physical_engine_error"
        assert payload["col"] == coords[0] and payload["row"] == coords[1]
        assert payload["attempts"] == 3
        assert payload["detail"] == "e3"
        assert payload["recovery_token"] == token

    def test_position_changed_counts_toward_the_same_episode_as_engine_error(self):
        sm = FakeSessionManager({"s1": FakeSession()})
        gateway = FakeGateway(
            outcomes=[
                PlatformMoveRejectedError("e1", reason="engine_error"),
                PlatformMoveRejectedError("e2", reason="position_changed"),
            ]
        )
        tracker = EngineRecoveryTracker(EngineRecoveryConfig(engine_move_max_attempts=2))
        orchestrator = FakeOrchestrator()
        app = _app(sm, gateway=gateway, tracker=tracker, orchestrator=orchestrator)
        vision = FakeVision()

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(), log))
        d2 = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(), log))

        assert d2 == 0.0  # tripped on the 2nd (shared episode, mixed reasons)
        assert len(orchestrator.entered) == 1

    def test_generic_exception_classified_as_engine_error_and_counts(self):
        sm = FakeSessionManager({"s1": FakeSession()})
        gateway = FakeGateway(outcomes=[RuntimeError("tunnel exploded")])
        tracker = EngineRecoveryTracker(EngineRecoveryConfig(engine_move_max_attempts=1))
        orchestrator = FakeOrchestrator()
        app = _app(sm, gateway=gateway, tracker=tracker, orchestrator=orchestrator)
        vision = FakeVision()

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(), log))

        assert delay == 0.0  # threshold=1 -> trips immediately
        assert len(orchestrator.entered) == 1
        assert sm.broadcasts[0][1]["detail"] == "tunnel exploded"


class TestPassthroughReasons:
    @pytest.mark.parametrize("reason", ["pending", "illegal_move", "move_rejected"])
    def test_passthrough_reasons_rearm_and_do_not_count(self, reason):
        sm = FakeSessionManager({"s1": FakeSession()})
        gateway = FakeGateway(outcomes=[PlatformMoveRejectedError("x", reason=reason)])
        tracker = EngineRecoveryTracker(EngineRecoveryConfig(engine_move_max_attempts=3))
        # Seed an existing episode to prove the passthrough reason doesn't touch it.
        tracker.on_failure(game_id="g1", coords=(3, 15), reason="engine_error")
        app = _app(sm, gateway=gateway, tracker=tracker)
        vision = FakeVision()

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(), log))

        assert delay == 0.5
        assert tracker.active_episode.count == 1  # untouched by the passthrough reason


class TestGameEndedReason:
    def test_game_ended_clears_episode_and_does_not_rearm(self):
        sm = FakeSessionManager({"s1": FakeSession()})
        gateway = FakeGateway(outcomes=[PlatformMoveRejectedError("over", reason="game_ended")])
        tracker = EngineRecoveryTracker()
        tracker.on_failure(game_id="g1", coords=(3, 15), reason="engine_error")
        app = _app(sm, gateway=gateway, tracker=tracker)
        vision = FakeVision()

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(), log))

        assert delay == 0.0
        assert tracker.active_episode is None
        assert vision.expected_pushes == []  # no re-arm


class TestSuccessClearsEpisode:
    def test_success_after_failures_clears_the_episode(self):
        sm = FakeSessionManager({"s1": FakeSession()})
        gateway = FakeGateway(outcomes=[PlatformMoveRejectedError("e1", reason="engine_error"), "ok"])
        tracker = EngineRecoveryTracker()
        app = _app(sm, gateway=gateway, tracker=tracker, orchestrator=None)
        vision = FakeVision()

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(), log))
        assert tracker.active_episode.count == 1

        d2 = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(), log))
        assert d2 == 0.0
        assert tracker.active_episode is None


class TestNoTrackerConfigured:
    def test_missing_tracker_falls_back_to_legacy_always_rearm(self):
        sm = FakeSessionManager({"s1": FakeSession()})
        gateway = FakeGateway(outcomes=[PlatformMoveRejectedError("boom", reason="engine_error")])
        app = _app(sm, gateway=gateway)  # no engine_recovery attribute at all
        vision = FakeVision()

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(), log))

        assert delay == 0.5
        assert vision.expected_pushes
