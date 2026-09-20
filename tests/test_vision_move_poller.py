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
        self.live_player_to_move = player_to_move  # NEW: the *live* game's turn
        self.ai_ladder_commit_lock = threading.RLock()  # NEW: real WebKaTrain has this (interface.py:199)
        self._state = {
            "stones": [],
            "board_size": [19, 19],
            "player_to_move": player_to_move,
            "current_node_id": 5150,
        }

    def get_state(self):
        return self._state

    def next_player_to_move(self):  # NEW
        return self.live_player_to_move

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
        self.expected_node_ids = []
        self.detected_board = None  # NEW: None = "no usable observation"
        self.observation_seq = 0  # NEW: which observation `detected_board` came from

    def set_expected_from_stones(self, stones, board_size=19, *, expected_node_id=None):
        self.expected_pushes.append(stones)
        self.expected_node_ids.append(expected_node_id)

    def get_board_observation(self):  # NEW
        return self.detected_board, self.observation_seq


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
    def test_rearm_forwards_current_node_id(self):
        sm = FakeSessionManager({"s1": FakeSession(player_to_move="W")})
        app = _app(sm, gateway=FakeGateway())
        vision = FakeVision()

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(color=BLACK), log))

        assert vision.expected_node_ids == [5150]

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


class TestEngineGameWhoseContextIsGone:
    def test_a_move_after_the_engine_game_ended_goes_to_the_gateway_not_the_local_tree(self):
        session = FakeSession(player_to_move="B")
        session.katrain.platform_engine_color = "W"
        gateway = FakeGateway(is_platform=False, outcomes=[PlatformMoveRejectedError("over", reason="game_ended")])
        vision = FakeVision()
        app = _app(FakeSessionManager({"s1": session}), gateway=gateway, tracker=EngineRecoveryTracker())

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(color=BLACK), log))

        assert gateway.calls == [("s1", 3, 15)]
        assert session.katrain.plays == []
        assert vision.expected_pushes == []
        assert delay == 0.0


class TestGameEndedIsRecordedOffRequest:
    def test_game_ended_is_recorded_off_request(self, monkeypatch):
        from unittest.mock import AsyncMock

        import katrain.web.server as server

        session = FakeSession()
        gateway = FakeGateway(outcomes=[PlatformMoveRejectedError("over", reason="game_ended")])
        app = _app(FakeSessionManager({"s1": session}), gateway=gateway, tracker=EngineRecoveryTracker())
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game_off_request", recorder)

        delay = asyncio.run(_handle_confirmed_move(app, FakeVision(), "s1", _move(), log))

        assert delay == 0.0
        recorder.assert_awaited_once_with(session, app)

    def test_other_rejections_record_nothing(self, monkeypatch):
        from unittest.mock import AsyncMock

        import katrain.web.server as server

        gateway = FakeGateway(outcomes=[PlatformMoveRejectedError("boom", reason="engine_error")])
        app = _app(FakeSessionManager({"s1": FakeSession()}), gateway=gateway, tracker=EngineRecoveryTracker())
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game_off_request", recorder)

        asyncio.run(_handle_confirmed_move(app, FakeVision(), "s1", _move(), log))

        recorder.assert_not_awaited()


def _board_with(cells):
    """19x19 vision board (row-major, 0=empty/1=black/2=white) with `cells` set."""
    board = [[0] * 19 for _ in range(19)]
    for (row, col), color in cells.items():
        board[row][col] = color
    return board


def _confirmed(col=3, row=3, color=BLACK, seq=0):
    return ConfirmedMove(col=col, row=row, color=color, observation_seq=seq)


# vision (row=3, col=3) -> katrain coords (col=3, 19-1-3=15). The gateway is called with
# katrain coords, so every "it was submitted" assertion below uses 15, not 3.
SUBMITTED = ("s1", 3, 15)


class TestSubmitTimePresenceRecheck:
    """L0a: confirm -> submit has a real gap (0.45s median, 3.02s measured worst case on
    RK3562 2026-09-20). A stone that vanished during that gap must not be committed.

    Two conditions must BOTH hold to cancel: the board reading is from an observation
    strictly newer than the one that confirmed the move, and the cell is empty in it.
    Anything else — no board, an observation no newer than the confirmation, an
    unreadable board — is "unknown", and unknown always submits. Dropping a real move
    is a worse failure than letting a rare phantom past the other three defences."""

    def test_move_dropped_when_a_newer_observation_shows_the_cell_empty(self):
        sm = FakeSessionManager({"s1": FakeSession(player_to_move="B")})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()
        vision.detected_board = _board_with({})
        vision.observation_seq = 12  # strictly newer than the confirmation below

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _confirmed(seq=11), log))

        assert delay == 0.5
        assert gateway.calls == []  # never reached the tunnel
        assert vision.expected_pushes  # re-armed so a real stone gets another chance

    def test_stale_observation_never_cancels(self):
        """THE regression this gate exists for: worker.py publishes status at 1 Hz, so
        the newest published board can predate the stone entirely. An observation that
        is not newer than the confirmation proves nothing."""
        sm = FakeSessionManager({"s1": FakeSession(player_to_move="B")})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()
        vision.detected_board = _board_with({})  # empty, but from BEFORE the stone landed
        vision.observation_seq = 11

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _confirmed(seq=11), log))

        assert gateway.calls == [SUBMITTED]

    def test_move_submitted_when_the_stone_is_still_present(self):
        """Deliberately asymmetric cell (row=3, col=15, not the row==col default the other
        tests in this class use): board[move_data.row][move_data.col] is populated, and
        board[move_data.col][move_data.row] is left empty, so a row/col transposition
        anywhere in the still_present indexing turns this red instead of staying green."""
        sm = FakeSessionManager({"s1": FakeSession(player_to_move="B")})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()
        vision.detected_board = _board_with({(3, 15): BLACK})
        vision.observation_seq = 12

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _confirmed(col=15, row=3, seq=11), log))

        # vision (row=3, col=15) -> katrain coords (col=15, 19-1-3=15).
        assert gateway.calls == [("s1", 15, 15)]

    def test_move_submitted_when_there_is_no_observation(self):
        sm = FakeSessionManager({"s1": FakeSession(player_to_move="B")})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()
        vision.detected_board = None
        vision.observation_seq = 99

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _confirmed(seq=11), log))

        assert gateway.calls == [SUBMITTED]

    def test_wrong_colour_at_the_cell_is_not_a_disappearance(self):
        """Only EMPTY cancels. A stone of the other colour is a colour misread, which the
        turn guard and the colour invariant handle — not a vanished stone."""
        sm = FakeSessionManager({"s1": FakeSession(player_to_move="B")})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()
        vision.detected_board = _board_with({(3, 3): WHITE})
        vision.observation_seq = 12

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _confirmed(seq=11), log))

        assert gateway.calls == [SUBMITTED]

    def test_unstamped_move_always_submits_even_if_the_cell_reads_empty(self):
        """seq 0 means "never stamped" (both workers bump their counter to >=1 in the same
        loop iteration, strictly before a confirmation can be stamped — see worker.py:362/483
        and worker_inprocess.py:417/531). Without a stamp there is no reference point, so
        comparing observed_seq against 0 would make ANY observation count as "newer" and
        collapse this into the naive "is the cell empty now?" check the design rejects."""
        sm = FakeSessionManager({"s1": FakeSession(player_to_move="B")})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()
        vision.detected_board = _board_with({})  # empty at the confirmed cell
        vision.observation_seq = 1  # > 0, would look "newer" than an unstamped move's seq

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _confirmed(seq=0), log))

        assert gateway.calls == [SUBMITTED]
        assert delay == 0.0


class TestPlatformTurnGuard:
    """L0b: the turn check at the top of _handle_confirmed_move reads
    session.last_state, which the code's own comment calls a possibly-stale
    broadcast frame. The local branch re-checks inside the commit lock via
    guard=True/expected_player; the cross-platform branch had no equivalent, so a
    move could reach the remote tunnel on a turn that had already passed."""

    def test_stale_broadcast_does_not_let_a_late_move_reach_the_tunnel(self):
        session = FakeSession(player_to_move="B")  # broadcast frame still says B
        session.katrain.live_player_to_move = "W"  # but the live game has moved on
        sm = FakeSessionManager({"s1": session})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(color=BLACK), log))

        assert delay == 0.5
        assert gateway.calls == []
        assert vision.expected_pushes  # re-armed

    def test_live_turn_agreeing_still_submits(self):
        session = FakeSession(player_to_move="B")
        session.katrain.live_player_to_move = "B"
        sm = FakeSessionManager({"s1": session})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(col=3, row=3, color=BLACK), log))

        assert gateway.calls == [SUBMITTED]  # katrain coords: row 3 flips to 19-1-3=15

    def test_unavailable_live_turn_does_not_block(self):
        """No game yet / accessor missing -> None -> fall back to the existing behaviour
        rather than refusing every move."""
        session = FakeSession(player_to_move="B")
        session.katrain.live_player_to_move = None
        sm = FakeSessionManager({"s1": session})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(col=3, row=3, color=BLACK), log))

        assert gateway.calls == [SUBMITTED]  # katrain coords: row 3 flips to 19-1-3=15
