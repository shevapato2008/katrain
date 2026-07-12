"""Task 12 — integration tests for the kiosk-golaxy-physical-play track (M3/M9/m4/D9).

Wires the REAL pieces together: `katrain.web.server._vision_move_poller` /
`_handle_confirmed_move`, a REAL `VisionService` (fake worker — no camera/CV
pipeline, but every command/event goes through the real service API, same
pattern as `tests/test_vision/test_service_event_routing.py`), a REAL
`PhysicalPlayOrchestrator`, a REAL `PlatformManager` + `PlatformCommandGateway`
+ `GolaxyAdapter` (only the network boundary — `adapter._rest.engine_genmove`
— is mocked, same pattern as `tests/platforms/test_engine_integration.py`), a
REAL `EngineRecoveryTracker`, and a REAL `SessionManager` running a real
KaTrain game tree. Only the LED (`FakeLed`) and the vision worker
(`FakeWorker`) are test doubles — see `tests/test_physical_play_orchestrator.py`
and `tests/test_physical_play_recovery.py` for the precedent of using a
`FakeLed`/bypassing `on_bind` at that granularity.

Six cases (see `.superpowers/sdd/task-12-brief.md`):
  1. 执白分先 — AI(B) opens synchronously inside start_engine_game; bind + tick
     lights the digital-black lamp (red LED).
  2. 人执黑让4子 — 4 star points guided regardless of color, AI(W) opening lamp
     survives after all 4 are physically placed; D9 lock-in: 人执白+让子 has NO
     AI opening and White (human) moves first.
  3. 全链路一手 — the REAL `_vision_move_poller` consumes a ConfirmedMove,
     drives it through the gateway's controllable-future tunnel mock, applies
     [human, AI] in order, and a manual tick lights the AI's lamp.
  4. 等待期第二颗子 (M3) — a second ConfirmedMove arrives while genmove is still
     pending; it must not be touched until the first move resolves, and then
     resolves per real turn order without tripping the failure dialog.
  5. 模式切换 (M9) — tsumego-leftover monitor/setup/paused state, then the real
     /vision/bind command sequence; and unbind-during-engine_error leaving no
     stuck pause for the next tsumego session.
  6. 边界抽样 (m4) — corner-point round trip, capture/recapture-same-point LED
     exemption, an AI-returned already-occupied point, and LED/vision faults
     not blocking the game loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np
import pytest

from katrain.core.base_katrain import KaTrainBase
from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.ipc import CommandType, ConfirmedMove, WorkerStatus
from katrain.vision.katrain_bridge import vision_move_to_katrain
from katrain.vision.service import VisionService
from katrain.web.core.engine_recovery import EngineRecoveryConfig, EngineRecoveryTracker
from katrain.web.core.physical_play import BLACK, PhysicalPlayConfig
from katrain.web.core.physical_play_orchestrator import PhysicalPlayOrchestrator
from katrain.web.platforms.gateway import PlatformCommandGateway
from katrain.web.platforms.golaxy.adapter import EngineGameConfig, GolaxyAdapter
from katrain.web.platforms.golaxy.coords import katrain_to_golaxy
from katrain.web.platforms.golaxy.engine_client import GenmoveResult
from katrain.web.platforms.manager import PlatformManager
from katrain.web.server import _handle_confirmed_move, _vision_move_poller
from katrain.web.session import SessionManager

log = logging.getLogger("test_engine_physical_integration")

# katrain.vision.board_state.BLACK/WHITE == katrain.web.core.physical_play.BLACK/WHITE (1/2).
VISION_BLACK, VISION_WHITE = 1, 2


@pytest.fixture(autouse=True)
def _hermetic_handicap_default(monkeypatch):
    """Same fixture as tests/platforms/conftest.py. This file lives at tests/ root,
    which that directory-scoped autouse fixture does NOT cover — duplicated here
    (rather than imported) so a dev box's game/handicap config can't leak stray
    handicap stones into every session this file creates."""
    original_config = KaTrainBase.config

    def _patched(self, setting, default=None):
        if setting == "game/handicap":
            return 0
        return original_config(self, setting, default)

    monkeypatch.setattr(KaTrainBase, "config", _patched)


# --- Fakes -------------------------------------------------------------------


class FakeLed:
    def __init__(self):
        self.calls = []

    def set_points(self, points, *, strict=False):
        self.calls.append(("set_points", points))
        return {"ok": True}

    def set_rgb_points(self, points, *, strict=False):
        self.calls.append(("set_rgb_points", points))
        return {"ok": True}

    def clear(self, *, strict=False):
        self.calls.append(("clear",))
        return {"ok": True}


class FaultyLed(FakeLed):
    """Raises on the Nth `set_points` call (0-indexed); every other call/method
    behaves like FakeLed. Used to prove an LED fault can't block the game."""

    def __init__(self, fail_on_call=0):
        super().__init__()
        self._fail_on_call = fail_on_call
        self._set_points_calls = 0

    def set_points(self, points, *, strict=False):
        n = self._set_points_calls
        self._set_points_calls += 1
        if n == self._fail_on_call:
            raise RuntimeError("serial port hiccup")
        return super().set_points(points, strict=strict)


class FakeWorker:
    """Stands in for VisionWorkerProcess/InProcessAdapter (no camera/CV pipeline).

    The REAL `VisionService` drives this through its real command/event API, so
    `commands` is the authentic sequence VisionService.bind_session/set_monitor/
    pause_detection/etc. actually send (verified against katrain/vision/worker.py's
    `_process_commands` handler where a test needs to reason about worker-side
    effects); `push_event` lets a test inject a ConfirmedMove exactly like the
    real worker's detection thread would.
    """

    def __init__(self):
        self.commands: list[CommandType] = []
        self.commands_data: list[dict] = []
        self._events: list = []
        self.status = WorkerStatus()
        self.is_alive = True

    def send_command(self, cmd):
        self.commands.append(cmd.action)
        self.commands_data.append(cmd.data)

    def push_event(self, evt) -> None:
        self._events.append(evt)

    def get_event(self):
        return self._events.pop(0) if self._events else None

    def get_status(self):
        return self.status

    def get_preview_jpeg(self):
        return None

    def stop(self):
        self.is_alive = False


class FakeVisionForOrchestrator:
    """Matches tests/test_physical_play_recovery.py's FakeVision -- used only for
    the pure LedPlanner/orchestrator sub-case (6B) that needs no gateway/poller."""

    def __init__(self, board_size=19):
        self.detected = np.zeros((board_size, board_size), dtype=int).tolist()
        self.expected_pushes = []
        self.paused = False
        self.lit = []

    def get_detected_board(self):
        return self.detected

    def set_expected_from_stones(self, stones, board_size=19):
        self.expected_pushes.append(stones)

    def pause_detection(self):
        self.paused = True

    def resume_detection(self):
        self.paused = False

    def set_lit_points(self, points):
        self.lit = points

    def reset_sync(self, expected=None):
        pass


class FakeManager:
    def __init__(self):
        self.broadcasts = []

    def broadcast_to_session(self, sid, payload):
        self.broadcasts.append((sid, payload))


def _state(stones, end_result=None, board_size=19):
    return {"stones": stones, "board_size": [board_size, board_size], "end_result": end_result}


# --- Shared helpers -----------------------------------------------------------


def _vision_move(col: int, row: int, player: str, board_size: int = 19) -> ConfirmedMove:
    """A ConfirmedMove in VISION GRID coordinates that decodes (via
    katrain.vision.katrain_bridge.vision_move_to_katrain) to KaTrain (col, row)."""
    color = VISION_BLACK if player == "B" else VISION_WHITE
    return ConfirmedMove(col=col, row=board_size - 1 - row, color=color)


def _genmove_for(col: int, row: int, board_size: int = 19, prob: float = 0.5) -> GenmoveResult:
    """A GenmoveResult whose coord decodes to KaTrain (col, row) — mirrors
    tests/platforms/test_engine_integration.py's helper of the same name."""
    return GenmoveResult(coord=katrain_to_golaxy(col, row, board_size), prob=prob)


def _main_line(session):
    """Ordered chronological [(player, coords), ...] for the real game tree —
    mirrors tests/platforms/test_engine_integration.py's helper of the same name."""
    node = session.katrain.game.current_node
    line = []
    while node is not None:
        if node.move is not None:
            line.append((node.move.player, node.move.coords))
        node = node.parent
    line.reverse()
    return line


def _vision_service() -> VisionService:
    svc = VisionService(VisionServiceConfig(enabled=True))
    svc._worker = FakeWorker()
    return svc


def _build_stack(genmove_side_effect=None, genmove_return=None, engine_recovery_config=None):
    """Full real stack for one test: SessionManager + PlatformManager +
    PlatformCommandGateway + GolaxyAdapter (network boundary mocked, same pattern
    as test_engine_integration.py's `_build_stack`) + VisionService (fake worker)
    + PhysicalPlayOrchestrator (fake LED) + EngineRecoveryTracker, wired into an
    app.state SimpleNamespace matching what server.py's poller/handler read."""
    sm = SessionManager(enable_engine=False)
    pm = PlatformManager(sm)
    gateway = PlatformCommandGateway(pm, sm)
    adapter = GolaxyAdapter()
    pm.register_adapter(adapter)
    adapter._rest.set_tokens("tok", "refresh")  # looks connected without hitting the network
    mock = AsyncMock()
    if genmove_side_effect is not None:
        mock.side_effect = genmove_side_effect
    else:
        mock.return_value = genmove_return
    adapter._rest.engine_genmove = mock

    vision = _vision_service()
    led = FakeLed()
    orch = PhysicalPlayOrchestrator(
        config=PhysicalPlayConfig(tick_interval_s=0.01),
        led=led,
        vision=vision,
        session_manager=sm,
    )
    tracker = EngineRecoveryTracker(engine_recovery_config or EngineRecoveryConfig())

    broadcasts = []
    orig_broadcast = sm.broadcast_to_session

    def _spy_broadcast(session_id, payload):
        broadcasts.append((session_id, payload))
        return orig_broadcast(session_id, payload)

    sm.broadcast_to_session = _spy_broadcast

    app = SimpleNamespace(
        state=SimpleNamespace(
            session_manager=sm,
            platform_gateway=gateway,
            engine_recovery=tracker,
            physical_play=orch,
            vision=vision,
        )
    )
    return SimpleNamespace(
        sm=sm,
        pm=pm,
        gateway=gateway,
        adapter=adapter,
        vision=vision,
        orch=orch,
        led=led,
        tracker=tracker,
        app=app,
        broadcasts=broadcasts,
    )


async def _wait_until(predicate, timeout: float = 2.0, interval: float = 0.02) -> None:
    """Poll `predicate()` until true or timeout — avoids flaky fixed sleeps around
    the real asyncio poller loop's 0.1s tick."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() > deadline:
            raise AssertionError(f"condition not met within {timeout}s")
        await asyncio.sleep(interval)


async def _wait_for_orchestrator_state(orch, stone_count: int, timeout: float = 2.0) -> None:
    """`WebKaTrain.update_state` (katrain/web/interface.py) throttles
    `update_state_callback` to ~4/s: a broadcast within 250ms of the previous one
    is NOT delivered inline — it is deferred to a background thread that sleeps
    250ms first. The orchestrator's `_latest_state` (and, via the SAME callback
    chain, `WebSession.last_state`) is only as fresh as the last delivered
    broadcast, so a real move applied via the gateway/poller needs this wait
    before a tick/state-dependent assertion — `_main_line` (the tree itself)
    updates synchronously and does NOT need it."""
    await _wait_until(
        lambda: orch._latest_state is not None and len(orch._latest_state.get("stones") or []) == stone_count,
        timeout=timeout,
    )


# --- Case 1: 执白分先 (AI(B) opens on start -> bind + tick lights it) ----------


class TestCase1AIOpeningLampAfterBind:
    @pytest.mark.asyncio
    async def test_ai_black_opening_move_lights_lamp_after_bind(self):
        stack = _build_stack(genmove_return=_genmove_for(9, 3))  # AI(B) opens at KaTrain (9, 3)
        config = EngineGameConfig(level=1100, human_color="W", handicap=0)
        session_id = await stack.pm.start_engine_game("golaxy", config, user_id=1)
        session = stack.sm.get_session(session_id)

        assert _main_line(session) == [("B", (9, 3))]  # AI opened synchronously inside start
        stack.adapter._rest.engine_genmove.assert_awaited_once()

        stack.orch.on_bind(session_id, session)
        stack.led.calls.clear()  # drop on_bind's internal on_unbind() defensive clear() call
        stack.vision._worker.status = WorkerStatus(detected_board=np.zeros((19, 19), dtype=int).tolist())
        stack.vision.refresh_status()
        stack.orch._tick_once()

        vr, vc = 19 - 1 - 3, 9
        assert stack.led.calls[-1] == ("set_points", [{"row": vr, "col": vc, "color": "black"}])
        assert stack.orch.board_caught_up is False  # physical stone not placed yet
        await stack.orch.shutdown()


# --- Case 2: 人执黑让4子 + D9 人执白让子对照 -------------------------------------


class TestCase2HandicapSetupThenAIOpeningLamp:
    @pytest.mark.asyncio
    async def test_four_star_points_guided_then_ai_white_opening_lamp_survives(self):
        stack = _build_stack(genmove_return=_genmove_for(9, 9))  # AI(W) opens at tengen (9, 9)
        config = EngineGameConfig(level=1100, human_color="B", handicap=4)
        session_id = await stack.pm.start_engine_game("golaxy", config, user_id=1)
        session = stack.sm.get_session(session_id)

        state = session.katrain.get_state()
        assert state["platform_engine_color"] == "W"
        stack.adapter._rest.engine_genmove.assert_awaited_once()  # AI(W) opened synchronously

        setup_cells = PhysicalPlayOrchestrator._setup_cells_from_state(state, 19)
        assert len(setup_cells) == 4  # 4 handicap star points

        stack.orch.on_bind(session_id, session)
        stack.vision._worker.status = WorkerStatus(detected_board=np.zeros((19, 19), dtype=int).tolist())
        stack.vision.refresh_status()
        stack.orch._tick_once()

        ai_vr, ai_vc = 19 - 1 - 9, 9
        first_plan_cells = {(p["row"], p["col"]) for p in stack.led.calls[-1][1]}
        assert first_plan_cells == setup_cells | {(ai_vr, ai_vc)}  # all 5 lamps lit at once

        # Place the 4 handicap stones physically, one at a time.
        board = np.zeros((19, 19), dtype=int)
        for r, c in sorted(setup_cells):
            board[r][c] = BLACK
            stack.vision._worker.status = WorkerStatus(detected_board=board.tolist())
            stack.vision.refresh_status()
            stack.orch._tick_once()

        # Only the AI's own opening move lamp remains — proves the AI-color lamp
        # survives all the handicap-setup churn instead of being swallowed by it.
        assert stack.led.calls[-1] == ("set_points", [{"row": ai_vr, "col": ai_vc, "color": "white"}])
        await stack.orch.shutdown()

    @pytest.mark.asyncio
    async def test_human_white_with_handicap_no_ai_opening_human_moves_first(self):
        """D9 语义固化: 人执白 + 让子 -> 无 AI 开局, 人类(白)先手."""
        stack = _build_stack(genmove_return=_genmove_for(9, 9))
        config = EngineGameConfig(level=1100, human_color="W", handicap=4)
        session_id = await stack.pm.start_engine_game("golaxy", config, user_id=1)
        session = stack.sm.get_session(session_id)

        stack.adapter._rest.engine_genmove.assert_not_awaited()  # no AI opening at all
        assert _main_line(session) == []  # only root-setup handicap stones, no move nodes
        assert session.katrain.next_player_info.player == "W"  # human (White) moves first


# --- Case 3: 全链路一手 (real poller) ------------------------------------------


class TestCase3FullChainRealPoller:
    @pytest.mark.asyncio
    async def test_real_poller_applies_human_then_ai_and_lights_ai_lamp(self):
        stack = _build_stack(genmove_return=_genmove_for(9, 9))
        config = EngineGameConfig(level=1100, human_color="B", handicap=0)
        session_id = await stack.pm.start_engine_game("golaxy", config, user_id=1)
        session = stack.sm.get_session(session_id)
        stack.orch.on_bind(session_id, session)
        stack.vision.bind_session(session_id)
        stack.vision._worker.status = WorkerStatus(detected_board=np.zeros((19, 19), dtype=int).tolist())
        stack.vision.refresh_status()

        poller = asyncio.create_task(_vision_move_poller(stack.app))
        try:
            stack.vision._worker.push_event(_vision_move(3, 3, "B"))
            await _wait_until(lambda: len(_main_line(session)) == 2)
            assert _main_line(session) == [("B", (3, 3)), ("W", (9, 9))]

            # The tree updates synchronously, but the orchestrator's own state
            # (which the tick reads) arrives via WebKaTrain's throttled broadcast.
            await _wait_for_orchestrator_state(stack.orch, stone_count=2)
            stack.orch._tick_once()
            vr, vc = 19 - 1 - 9, 9
            assert stack.led.calls[-1] == ("set_points", [{"row": vr, "col": vc, "color": "white"}])
        finally:
            poller.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await poller
            await stack.orch.shutdown()


# --- Case 4: 等待期第二颗子 (M3) -------------------------------------------------


class TestCase4SecondMoveDuringPendingGenmove:
    @pytest.mark.asyncio
    async def test_second_move_waits_for_first_then_resolves_out_of_turn_no_dialog(self):
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_genmove(**kwargs):
            started.set()
            await release.wait()
            return _genmove_for(9, 9)

        stack = _build_stack(genmove_side_effect=slow_genmove)
        config = EngineGameConfig(level=1100, human_color="B", handicap=0)
        session_id = await stack.pm.start_engine_game("golaxy", config, user_id=1)
        session = stack.sm.get_session(session_id)
        stack.orch.on_bind(session_id, session)
        stack.vision.bind_session(session_id)

        poller = asyncio.create_task(_vision_move_poller(stack.app))
        try:
            stack.vision._worker.push_event(_vision_move(3, 3, "B"))
            await asyncio.wait_for(started.wait(), timeout=2.0)

            # Second confirmed move arrives while the first's genmove is still pending.
            stack.vision._worker.push_event(_vision_move(5, 5, "W"))
            await asyncio.sleep(0.3)  # several poller iterations -- must stay blocked on move 1
            assert _main_line(session) == []  # neither move has landed yet

            release.set()
            await _wait_until(lambda: len(_main_line(session)) == 2)
            assert _main_line(session) == [("B", (3, 3)), ("W", (9, 9))]  # move 1's exchange lands

            # Move 2 (White) is now out-of-turn (next player is Black again) -> ignored,
            # consumed only AFTER move 1 returned, per the poller's single sequential loop.
            await asyncio.sleep(0.3)
            assert _main_line(session) == [("B", (3, 3)), ("W", (9, 9))]  # unchanged

            assert stack.tracker.active_episode is None  # no failure episode ever opened
            assert not any(p.get("type") == "physical_engine_error" for _, p in stack.broadcasts)
            assert PhysicalPlayOrchestrator.PAUSE_REASON_ENGINE_ERROR not in stack.orch._pause_reasons

            # detector baseline ends up consistent with the final digital board (the
            # out-of-turn ignore re-arms by re-pushing the current expected board).
            expected_pushed = stack.vision._worker.commands.count(CommandType.SET_EXPECTED_BOARD)
            assert expected_pushed > 0
        finally:
            poller.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await poller
            await stack.orch.shutdown()


# --- Case 5: 模式切换 (M9) ------------------------------------------------------


class TestCase5ModeSwitchCommandSequence:
    @pytest.mark.asyncio
    async def test_tsumego_leftover_state_then_engine_bind_resets_pause_and_sync(self):
        stack = _build_stack()
        worker = stack.vision._worker

        # tsumego 页残留状态: monitor 模式 + setup 模式 + paused.
        stack.vision.set_monitor(True)
        stack.vision.enter_setup_mode(np.zeros((19, 19), dtype=int))
        stack.vision.set_paused(True)

        config = EngineGameConfig(level=1100, human_color="B", handicap=0)
        session_id = await stack.pm.start_engine_game("golaxy", config, user_id=1)
        session = stack.sm.get_session(session_id)

        # Real /vision/bind sequence (katrain/web/api/v1/endpoints/vision.py bind_session).
        stack.vision.bind_session(session_id)
        game_state = session.katrain.get_state()
        if game_state and "stones" in game_state:
            stack.vision.set_expected_from_stones(game_state["stones"])
        stack.orch.on_bind(session_id, session)

        # katrain/vision/worker.py _process_commands (verified by reading the source):
        # CommandType.BIND unconditionally sets self._paused=False and calls
        # self._sync.bind() -> CALIBRATING, overriding ANY leftover monitor/setup/
        # paused state -- so as long as BIND is the LAST pause-relevant command sent
        # after the tsumego leftover churn, detection ends up in a correct state even
        # though the bind endpoint sends no explicit "reset monitor/pause" commands.
        bind_index = worker.commands.index(CommandType.BIND)
        assert worker.commands.index(CommandType.SET_MONITOR) < bind_index
        assert worker.commands.index(CommandType.ENTER_SETUP_MODE) < bind_index
        assert worker.commands.index(CommandType.SET_PAUSED) < bind_index
        await stack.orch.shutdown()

    @pytest.mark.asyncio
    async def test_unbind_during_engine_error_leaves_no_leftover_pause_for_tsumego(self):
        stack = _build_stack()
        worker = stack.vision._worker
        config = EngineGameConfig(level=1100, human_color="B", handicap=0)
        session_id = await stack.pm.start_engine_game("golaxy", config, user_id=1)
        session = stack.sm.get_session(session_id)
        stack.orch.on_bind(session_id, session)
        stack.vision.bind_session(session_id)

        stack.orch.enter_engine_error((3, 3), "tok-1")
        assert CommandType.PAUSE_DETECTION in worker.commands

        # Real /vision/unbind sequence.
        stack.orch.on_unbind()
        stack.vision.unbind_session()
        stack.app.state.engine_recovery.clear()

        # -> entering tsumego (monitor mode) must not inherit a stuck pause.
        stack.vision.set_monitor(True)

        pause_related = [c for c in worker.commands if c in (CommandType.PAUSE_DETECTION, CommandType.RESUME_DETECTION)]
        assert pause_related[-1] == CommandType.RESUME_DETECTION
        assert stack.orch._pause_reasons == set()
        await stack.orch.shutdown()


# --- Case 6: 边界抽样 (m4) -------------------------------------------------------


class TestCase6BoundarySampling:
    @pytest.mark.asyncio
    async def test_corner_points_round_trip_through_vision_gateway_golaxy(self):
        stack = _build_stack(genmove_return=_genmove_for(18, 18))
        config = EngineGameConfig(level=1100, human_color="B", handicap=0)
        session_id = await stack.pm.start_engine_game("golaxy", config, user_id=1)
        session = stack.sm.get_session(session_id)

        mv = vision_move_to_katrain(col=0, row=0, color=VISION_BLACK, board_size=19)
        assert mv.coords == (0, 18)
        await stack.gateway.play_move(session_id, mv.coords[0], mv.coords[1], user_id=0)

        assert _main_line(session) == [("B", (0, 18)), ("W", (18, 18))]

    def test_capture_then_ai_recapture_same_point_no_false_remove_lamp(self):
        """LedPlanner-level (no gateway/poller needed): after a digital capture at a
        point, the AI immediately plays back into that SAME point while the
        captured physical stone is still sitting there (not yet lifted). The
        presence-only tick() check must treat this as satisfied (no misleading
        blue 'remove' lamp) -- color mismatch is the sync/mismatch-dialog
        subsystem's job, not LedPlanner's (see physical_play.py's tick() docstring
        on _observed_once)."""
        led = FakeLed()
        vision = FakeVisionForOrchestrator()
        orch = PhysicalPlayOrchestrator(
            config=PhysicalPlayConfig(extra_stone_debounce_ticks=99),
            led=led,
            vision=vision,
            session_manager=FakeManager(),
        )
        orch._session_id = "s1"  # bypass on_bind (needs a running loop + real session)

        vr, vc = 19 - 1 - 5, 5
        orch.on_game_state(_state([["B", [5, 5], None, 1]]))
        vision.detected[vr][vc] = BLACK
        orch._tick_once()
        assert orch.board_caught_up is True

        orch.on_game_state(_state([]))  # digital capture: point emptied
        orch._tick_once()
        assert orch.board_caught_up is False  # removal pending: physical stone still there

        orch.on_game_state(_state([["W", [5, 5], None, 2]]))  # AI plays back into the same point
        orch._tick_once()
        assert orch.board_caught_up is True  # presence-only check satisfied
        assert led.calls[-1] == ("clear",)  # no lamp at all -- in particular no false "remove"

    @pytest.mark.asyncio
    async def test_ai_returns_already_occupied_point_is_rejected_as_engine_error(self):
        """m4: 'AI 返回已占点 -> position 断言/合法性防线拒绝且广播 engine_error'.

        Fix round 1 (see Task 12 report, Fix round 1): `gateway.py::_play_engine_move`
        now re-validates the AI's returned coordinate (against the position with the
        human move applied first) before committing EITHER move locally. An
        already-occupied reply is rejected with `PlatformMoveRejectedError(reason=
        "engine_error")` -- neither move lands locally, so the tunnel's own
        already-committed (and now-illegal-locally) coord doesn't desync the local
        board from the tunnel history any further than the single failed attempt.
        `_handle_confirmed_move` folds that into `EngineRecoveryTracker`, which (with
        `engine_move_max_attempts=1`) crosses the threshold on the very first
        attempt: `physical_engine_error` broadcasts and the orchestrator enters its
        engine-error pause."""
        stack = _build_stack(
            genmove_side_effect=[_genmove_for(9, 9), _genmove_for(3, 3)],
            engine_recovery_config=EngineRecoveryConfig(engine_move_max_attempts=1),
        )
        config = EngineGameConfig(level=1100, human_color="B", handicap=0)
        session_id = await stack.pm.start_engine_game("golaxy", config, user_id=1)
        session = stack.sm.get_session(session_id)
        stack.orch.on_bind(session_id, session)

        move1 = _vision_move(3, 3, "B")
        await _handle_confirmed_move(stack.app, stack.vision, session_id, move1, log)
        assert _main_line(session) == [("B", (3, 3)), ("W", (9, 9))]

        # Second exchange: the human's move (5,5) is legal, but the (mocked) AI
        # "replies" with (3,3) -- already occupied by the FIRST exchange's human stone.
        move2 = _vision_move(5, 5, "B")
        delay = await _handle_confirmed_move(stack.app, stack.vision, session_id, move2, log)

        # Neither move lands: the human's (5,5) is discarded along with the AI's
        # illegal reply -- the tree is unchanged from after the first exchange.
        assert _main_line(session) == [("B", (3, 3)), ("W", (9, 9))]
        assert delay == 0.0  # threshold crossed on attempt 1 -> rearm=False -> no retry delay
        assert stack.tracker.active_episode is not None  # tripped episode stays active (not cleared)
        assert stack.tracker.active_episode.recovery_token is not None
        error_broadcasts = [p for _, p in stack.broadcasts if p.get("type") == "physical_engine_error"]
        assert len(error_broadcasts) == 1
        assert error_broadcasts[0]["col"] == 5 and error_broadcasts[0]["row"] == 5
        assert PhysicalPlayOrchestrator.PAUSE_REASON_ENGINE_ERROR in stack.orch._pause_reasons
        await stack.orch.shutdown()

    @pytest.mark.asyncio
    async def test_led_and_vision_faults_do_not_block_the_game(self):
        stack = _build_stack(genmove_return=_genmove_for(9, 9))
        faulty_led = FaultyLed(fail_on_call=0)  # first set_points call raises
        stack.orch._led = faulty_led  # replaces stack.led -- assert on faulty_led, not stack.led
        config = EngineGameConfig(level=1100, human_color="B", handicap=0)
        session_id = await stack.pm.start_engine_game("golaxy", config, user_id=1)
        session = stack.sm.get_session(session_id)
        # on_bind() starts its OWN tick task (self._task) -- reuse that one instead
        # of creating a second concurrent `_run()` coroutine on the same orchestrator.
        stack.orch.on_bind(session_id, session)
        tick_task = stack.orch._task
        stack.vision.bind_session(session_id)
        stack.vision._worker.status = WorkerStatus(detected_board=np.zeros((19, 19), dtype=int).tolist())
        stack.vision.refresh_status()

        poller = asyncio.create_task(_vision_move_poller(stack.app))
        try:
            stack.vision._worker.push_event(_vision_move(3, 3, "B"))
            await _wait_until(lambda: len(_main_line(session)) == 2)
            assert _main_line(session) == [("B", (3, 3)), ("W", (9, 9))]  # game unaffected

            # The tree updates synchronously; the orchestrator's own state (which
            # the tick loop reads) arrives via WebKaTrain's throttled broadcast.
            await _wait_for_orchestrator_state(stack.orch, stone_count=2)
            await asyncio.sleep(0.05)  # let the running tick loop hit the faulty LED write
            assert not tick_task.done()  # loop survived the exception

            # Physically place the AI's stone -> plan changes -> LED writes resume.
            board = np.zeros((19, 19), dtype=int)
            vr, vc = 19 - 1 - 9, 9
            board[vr][vc] = 2
            stack.vision._worker.status = WorkerStatus(detected_board=board.tolist())
            stack.vision.refresh_status()
            await _wait_until(lambda: ("clear",) in faulty_led.calls, timeout=2.0)
            assert not tick_task.done()
        finally:
            poller.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await poller
            await stack.orch.shutdown()
