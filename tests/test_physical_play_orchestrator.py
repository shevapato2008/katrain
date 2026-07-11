"""Orchestrator: game state + observed board -> LED writes, catch-up gate, reminder."""

import asyncio
import copy
import json
import os
import time

import numpy as np
import pytest

from katrain.web.core.physical_play import BLACK, WHITE, PhysicalPlayConfig
from katrain.web.core.physical_play_orchestrator import PhysicalPlayOrchestrator

# Task 1 contract fixture: a real engine-game get_state() dump (both players marked
# "human"; platform_engine_color:"W" is the only signal that W is the remote Golaxy AI).
ENGINE_GAME_STATE_FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "katrain",
    "web",
    "ui",
    "src",
    "kiosk",
    "__tests__",
    "fixtures",
    "engine_game_state.json",
)


def _load_engine_game_state_fixture():
    with open(ENGINE_GAME_STATE_FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


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


class FakeVision:
    def __init__(self):
        self.detected = np.zeros((19, 19), dtype=int).tolist()
        self.expected_pushes = []
        self.paused = False
        self.lit = []
        self.calls = []  # ordered ("pause"|"resume") sequence — dup-call detector

    def get_detected_board(self):
        return self.detected

    def set_expected_from_stones(self, stones, board_size=19):
        self.expected_pushes.append(stones)

    def pause_detection(self):
        self.paused = True
        self.calls.append("pause")

    def resume_detection(self):
        self.paused = False
        self.calls.append("resume")

    def set_lit_points(self, points):
        self.lit = points


class FakeManager:
    def __init__(self):
        self.broadcasts = []

    def broadcast_to_session(self, sid, payload):
        self.broadcasts.append((sid, payload))


def state(stones, end_result=None):
    return {"stones": stones, "board_size": [19, 19], "end_result": end_result}


def _orch(clock=lambda: 0.0, **cfg):
    led, vision, mgr = FakeLed(), FakeVision(), FakeManager()
    orch = PhysicalPlayOrchestrator(
        config=PhysicalPlayConfig(**cfg),
        led=led,
        vision=vision,
        session_manager=mgr,
        touch_led_activity=lambda: None,
        clock=clock,
    )
    orch._session_id = "s1"  # bypass on_bind (needs a running loop + real session)
    return orch, led, vision, mgr


class TestTick:
    def test_ai_stone_lights_then_clears_when_placed(self):
        orch, led, vision, _ = _orch()
        orch.on_game_state(state([["B", [3, 15], None, 1]]))  # GTP y=15 -> row 3
        orch._tick_once()
        assert led.calls[-1] == ("set_points", [{"row": 3, "col": 3, "color": "black"}])
        assert orch.board_caught_up is False
        vision.detected[3][3] = 1  # 用户替 AI 摆好
        orch._tick_once()
        assert led.calls[-1] == ("clear",)
        assert orch.board_caught_up is True

    def test_no_led_rewrite_when_plan_unchanged(self):
        orch, led, vision, _ = _orch()
        orch.on_game_state(state([["B", [3, 15], None, 1]]))
        orch._tick_once()
        n = len(led.calls)
        orch._tick_once()
        assert len(led.calls) == n  # 去重：不重复写串口

    def test_game_end_clears_lamps(self):
        orch, led, vision, _ = _orch()
        orch.on_game_state(state([["B", [3, 15], None, 1]], end_result="W+R"))
        orch._tick_once()
        assert led.calls[-1] == ("clear",)

    def test_expected_pushed_to_vision_on_every_state(self):
        orch, _, vision, _ = _orch()
        orch.on_game_state(state([["B", [3, 15], None, 1]]))
        assert len(vision.expected_pushes) == 1  # AI 落子后立即 force_sync 基线


class TestReminder:
    def test_reminder_then_escalation(self):
        now = [0.0]
        orch, _, vision, mgr = _orch(clock=lambda: now[0], reminder_after_s=30.0, escalate_after_s=120.0)
        orch.on_game_state(state([["B", [3, 15], None, 1]]))
        orch._tick_once()  # behind since t=0（首 tick 只记时，不广播）
        now[0] = 31.0
        orch._tick_once()
        assert [b[1]["data"]["kind"] for b in mgr.broadcasts] == ["reminder"]
        assert mgr.broadcasts[0][1]["data"]["to_place"] == [[3, 3]]
        now[0] = 121.0
        orch._tick_once()  # 评审 B 逃生舱：升级为对话框
        assert [b[1]["data"]["kind"] for b in mgr.broadcasts] == ["reminder", "escalation"]
        now[0] = 122.0
        orch._tick_once()
        assert len(mgr.broadcasts) == 2  # 各档只发一次

    def test_counters_reset_when_caught_up(self):
        now = [0.0]
        orch, _, vision, mgr = _orch(clock=lambda: now[0])
        orch.on_game_state(state([["B", [3, 15], None, 1]]))
        orch._tick_once()
        vision.detected[3][3] = 1
        now[0] = 40.0
        orch._tick_once()  # 追平 → 计时器/已发标志复位
        assert mgr.broadcasts == []


class TestPauseDrive:
    """Q4 重设计：盘面未追平 → 暂停 worker 落子确认；追平 → 恢复（编排器唯一 owner）。"""

    def test_detection_paused_while_behind_resumed_when_caught_up(self):
        orch, _, vision, _ = _orch()
        orch.on_game_state(state([["B", [3, 15], None, 1]]))
        orch._tick_once()  # AI 子未摆 → 暂停确认
        assert vision.paused is True
        vision.detected[3][3] = 1
        orch._tick_once()  # 追平 → 恢复
        assert vision.paused is False


class TestLedReassert:
    """评审 A：非空灯态周期重申，击穿 300s 失效保护 + 从手动清灯恢复。"""

    def test_lamps_reasserted_before_idle_failsafe(self):
        now = [0.0]
        orch, led, vision, _ = _orch(clock=lambda: now[0], led_reassert_interval_s=240.0)
        orch.on_game_state(state([["B", [3, 15], None, 1]]))
        orch._tick_once()
        assert len([c for c in led.calls if c[0] == "set_points"]) == 1
        now[0] = 100.0
        orch._tick_once()  # 未到间隔：去重生效，不重发
        assert len([c for c in led.calls if c[0] == "set_points"]) == 1
        now[0] = 241.0
        orch._tick_once()  # 重申：同一批次再发（并盖活动戳）
        assert len([c for c in led.calls if c[0] == "set_points"]) == 2


class TestHint:
    def test_show_hint_suspends_and_blinks_then_restores(self):
        # 真实时钟：blink 的 deadline 用注入 clock 判定，固定 0.0 的假钟永不超时
        orch, led, vision, _ = _orch(clock=time.monotonic, hint_blink_period_s=0.02, hint_timeout_s=0.05)

        async def run():
            orch.show_hint([(3, 3), (15, 15)])
            assert vision.paused is True
            await asyncio.sleep(0.15)  # 超时自然结束

        asyncio.run(run())
        assert vision.paused is False  # 检测恢复
        rgb_calls = [c for c in led.calls if c[0] == "set_rgb_points"]
        assert rgb_calls and rgb_calls[0][1][0]["rgb"] == (255, 255, 255)

    def test_dismiss_hint_restores_immediately(self):
        orch, led, vision, _ = _orch(clock=time.monotonic, hint_blink_period_s=0.02, hint_timeout_s=10.0)

        async def run():
            orch.show_hint([(3, 3)])
            await asyncio.sleep(0.03)
            orch.dismiss_hint()
            assert vision.paused is False

        asyncio.run(run())


class TestPauseReasonsMatrix:
    """M2: self._pause_reasons (set) replaces the _suspended/_hint_active shared
    booleans. Task 7 (engine_error) isn't built yet, so these tests poke the
    internal _add_pause_reason/_remove_pause_reason API directly as a stand-in.
    Contract asserted here: detection pause = ANY reason present; tick suspension
    (orch._suspended) = any reason OTHER than pure "lag" (lag alone must never stop
    the tick -- the tick is what re-evaluates catch-up and clears the lag reason)."""

    def test_hint_then_engine_error_dismiss_hint_still_paused(self):
        orch, _, vision, _ = _orch(clock=time.monotonic, hint_timeout_s=10.0)

        async def run():
            orch.show_hint([(3, 3)])
            assert vision.paused is True
            assert orch._suspended is True
            orch._add_pause_reason("engine_error")  # Task 7 stand-in
            orch.dismiss_hint()
            assert "hint" not in orch._pause_reasons
            assert vision.paused is True  # engine_error keeps detection paused
            assert orch._suspended is True  # ... and keeps the tick suspended too

        asyncio.run(run())
        assert vision.calls == ["pause"]  # hint->error handoff must not re-pause/resume

    def test_engine_error_then_hint_show_dismiss_error_persists(self):
        orch, _, vision, _ = _orch(clock=time.monotonic, hint_timeout_s=10.0)
        orch._add_pause_reason("engine_error")
        assert vision.paused is True

        async def run():
            orch.show_hint([(3, 3)])
            assert vision.paused is True
            orch.dismiss_hint()
            assert vision.paused is True  # error still set
            assert orch._suspended is True

        asyncio.run(run())
        assert vision.calls == ["pause"]  # no duplicate calls across the hint show/dismiss

    def test_lag_alone_pauses_detection_but_not_tick(self):
        orch, _, vision, _ = _orch()
        orch._add_pause_reason("lag")
        assert vision.paused is True
        assert orch._suspended is False  # tick keeps running so it can clear the lag itself
        assert vision.calls == ["pause"]

    def test_lag_plus_hint_suspends_tick_then_hint_dismiss_leaves_lag_pause(self):
        orch, _, vision, _ = _orch(clock=time.monotonic, hint_timeout_s=10.0)
        orch._add_pause_reason("lag")
        assert orch._suspended is False

        async def run():
            orch.show_hint([(3, 3)])
            assert orch._suspended is True  # hint suspends the tick on top of lag
            assert vision.paused is True
            orch.dismiss_hint()
            assert orch._suspended is False  # lag alone no longer suspends the tick
            assert vision.paused is True  # but detection stays paused: lag persists

        asyncio.run(run())
        assert vision.calls == ["pause"]  # lag's initial pause is never re-sent/duplicated

    def test_on_unbind_clears_all_reasons_and_resumes(self):
        orch, _, vision, _ = _orch()
        orch._add_pause_reason("lag")
        orch._add_pause_reason("engine_error")
        assert vision.paused is True
        orch.on_unbind()
        assert orch._pause_reasons == set()
        assert orch._suspended is False
        assert vision.paused is False
        assert vision.calls == ["pause", "resume"]  # exactly one resume, no duplicates

    def test_idempotent_add_remove_do_not_duplicate_ipc_calls(self):
        orch, _, vision, _ = _orch()
        orch._add_pause_reason("lag")
        orch._add_pause_reason("lag")  # already present: no-op
        assert vision.calls == ["pause"]
        orch._remove_pause_reason("lag")
        orch._remove_pause_reason("lag")  # already absent: no-op
        assert vision.calls == ["pause", "resume"]


class TestEngineErrorPauseReason:
    """Task 7 (B5/M1/M4): enter_engine_error/clear_engine_error are the orchestrator's
    half of the recovery hand-off -- the poller calls enter_engine_error once an
    engine_recovery episode trips its threshold, so detection stays paused (no more
    ConfirmedMove) until the frontend dismisses (Task 8/9)."""

    def test_enter_engine_error_adds_pause_reason_and_stores_context(self):
        orch, _, vision, _ = _orch()
        orch.enter_engine_error((3, 3), "tok-123")
        assert PhysicalPlayOrchestrator.PAUSE_REASON_ENGINE_ERROR in orch._pause_reasons
        assert vision.paused is True
        assert orch._suspended is True  # engine_error suspends the tick too, like hint
        assert vision.calls == ["pause"]

    def test_clear_engine_error_removes_pause_reason(self):
        orch, _, vision, _ = _orch()
        orch.enter_engine_error((3, 3), "tok-123")
        orch.clear_engine_error()
        assert PhysicalPlayOrchestrator.PAUSE_REASON_ENGINE_ERROR not in orch._pause_reasons
        assert vision.paused is False
        assert orch._suspended is False
        assert vision.calls == ["pause", "resume"]

    def test_engine_error_coexists_with_lag_like_hint(self):
        orch, _, vision, _ = _orch()
        orch._add_pause_reason("lag")
        orch.enter_engine_error((3, 3), "tok-123")
        orch.clear_engine_error()
        assert orch._suspended is False  # tick resumes (lag alone doesn't suspend it)
        assert vision.paused is True  # but detection stays paused: lag persists
        assert vision.calls == ["pause"]  # single pause call, no duplicate

    def test_on_unbind_clears_engine_error_too(self):
        orch, _, vision, _ = _orch()
        orch.enter_engine_error((3, 3), "tok-123")
        orch.on_unbind()
        assert orch._pause_reasons == set()
        assert vision.paused is False

    def test_idempotent_enter_and_clear(self):
        orch, _, vision, _ = _orch()
        orch.enter_engine_error((3, 3), "tok-123")
        orch.enter_engine_error((3, 3), "tok-123")  # no-op re-add
        assert vision.calls == ["pause"]
        orch.clear_engine_error()
        orch.clear_engine_error()  # no-op re-remove
        assert vision.calls == ["pause", "resume"]


class FakeKatrainForBind:
    def __init__(self, state):
        self.update_state_callback = None
        self._state = state

    def get_state(self):
        return self._state


class FakeSessionForBind:
    def __init__(self, state):
        self.katrain = FakeKatrainForBind(state)


class TestBindLifecycle:
    def test_on_bind_wraps_chains_seeds_starts_then_unbind_restores_and_shutdown(self):
        led, vision, mgr = FakeLed(), FakeVision(), FakeManager()
        orch = PhysicalPlayOrchestrator(
            config=PhysicalPlayConfig(),
            led=led,
            vision=vision,
            session_manager=mgr,
            touch_led_activity=lambda: None,
            clock=lambda: 0.0,
        )
        orig_calls = []
        st = state([["B", [3, 15], None, 1]])

        async def run():
            sess = FakeSessionForBind(st)
            sess.katrain.update_state_callback = lambda s: orig_calls.append(s)
            orch.on_bind("s1", sess)
            wrapped = sess.katrain.update_state_callback
            assert wrapped is not None
            assert len(vision.expected_pushes) == 1  # on_bind seeded expected board
            assert orch._task is not None and not orch._task.done()  # tick loop started
            new_st = state([["B", [3, 15], None, 1], ["W", [4, 15], None, 2]])
            wrapped(new_st)
            assert orig_calls[-1] is new_st  # original callback chained first
            assert len(vision.expected_pushes) == 2  # orchestrator.on_game_state pushed
            orch.on_bind("s1", sess)  # idempotent for same session
            assert sess.katrain.update_state_callback is wrapped
            orch.on_unbind()  # restores original callback
            assert sess.katrain.update_state_callback is not wrapped
            await orch.shutdown()
            assert orch._task is None

        asyncio.run(run())


class TestGuidanceContextExtraction:
    """AI 颜色 + 让子格从 game_update state 中提取（改动 1 的输入侧）。"""

    def test_guided_colors_human_black_vs_ai_white(self):
        state = {
            "players_info": {
                "B": {"player_type": "player:human"},
                "W": {"player_type": "player:ai"},
            }
        }
        assert PhysicalPlayOrchestrator._guided_colors_from_state(state) == {2}  # WHITE only

    def test_guided_colors_both_human_empty_set(self):
        state = {
            "players_info": {
                "B": {"player_type": "player:human"},
                "W": {"player_type": "player:human"},
            }
        }
        assert PhysicalPlayOrchestrator._guided_colors_from_state(state) == set()

    def test_guided_colors_missing_players_info_returns_none(self):
        assert PhysicalPlayOrchestrator._guided_colors_from_state({}) is None  # legacy guide-all

    def test_guided_colors_platform_engine_color_white_from_contract_fixture(self):
        # Task 1 contract fixture: real engine-game state, both players "human",
        # platform_engine_color:"W" is the only marker that W is the remote Golaxy AI.
        state = _load_engine_game_state_fixture()
        assert state["platform_engine_color"] == "W"
        assert PhysicalPlayOrchestrator._guided_colors_from_state(state) == {WHITE}

    def test_guided_colors_platform_engine_color_black(self):
        state = _load_engine_game_state_fixture()
        state["platform_engine_color"] = "B"
        assert PhysicalPlayOrchestrator._guided_colors_from_state(state) == {BLACK}

    def test_guided_colors_platform_engine_color_none_no_regression(self):
        # Field present but None (local pvp / remote-platform games without an engine
        # seat) must fall back to the existing player_type-only behavior: both human ->
        # empty set, NOT guide-all.
        state = _load_engine_game_state_fixture()
        state["platform_engine_color"] = None
        assert PhysicalPlayOrchestrator._guided_colors_from_state(state) == set()

    def test_guided_colors_platform_engine_color_absent_no_regression(self):
        # Field absent entirely (older state / non-engine platform) must not regress
        # the existing player_type-only behavior either.
        state = _load_engine_game_state_fixture()
        del state["platform_engine_color"]
        assert PhysicalPlayOrchestrator._guided_colors_from_state(state) == set()

    def test_guided_colors_player_ai_branch_unaffected_by_engine_color(self):
        # player:ai still guides regardless of platform_engine_color (which is None for
        # local AI games) -- no regression to the pre-existing branch.
        state = {
            "players_info": {
                "B": {"player_type": "player:human"},
                "W": {"player_type": "player:ai"},
            },
            "platform_engine_color": None,
        }
        assert PhysicalPlayOrchestrator._guided_colors_from_state(state) == {WHITE}

    def test_setup_cells_from_root_stones(self):
        # stones entry: [player, [col, gtp_row], score_loss, move_number]; move_number None = 让子/AB
        state = {
            "stones": [
                ["B", [3, 15], None, None],  # handicap stone, gtp_row 15 -> vision row 3
                ["B", [15, 3], None, None],  # handicap stone
                ["W", [16, 16], 0.5, 1],  # played move -> excluded
            ]
        }
        cells = PhysicalPlayOrchestrator._setup_cells_from_state(state, 19)
        assert cells == {(3, 3), (15, 15)}

    def test_setup_cells_empty_for_no_stones(self):
        assert PhysicalPlayOrchestrator._setup_cells_from_state({}, 19) == set()


class TestLitPointsIncludeAllLamps:
    """遮蔽语义在 board_state（只挡新增、不逐已有子）；orchestrator 上报完整点集，
    这样拿走棋子后蓝灯裸照空格的眩光仍然被挡住，不会变成幻影子。"""

    def test_all_lamp_points_sent_as_lit(self):
        orch, led, vision, mgr = _orch()
        orch._apply_points(
            [
                {"row": 3, "col": 3, "color": "black"},
                {"row": 5, "col": 5, "color": "remove"},
            ]
        )
        assert vision.lit == [(3, 3), (5, 5)]


class TestEngineGameGuidance:
    """Integration smoke (G1): an engine game (Golaxy AI plays via platform_engine_color,
    both players_info marked human) must guide the AI's color exactly like a local
    player:ai opponent would — closing the gap where engine moves got no lamp."""

    def test_engine_ai_white_move_gets_white_lamp(self):
        orch, led, vision, _ = _orch()
        fixture = _load_engine_game_state_fixture()
        assert fixture["platform_engine_color"] == "W"
        st = copy.deepcopy(fixture)
        st["stones"] = [["W", [3, 15], None, 1]]  # GTP y=15 -> vision row 3, col 3
        orch.on_game_state(st)
        # Physical board still lacks the stone (vision.detected stays all zeros).
        orch._tick_once()
        assert led.calls[-1] == ("set_points", [{"row": 3, "col": 3, "color": "white"}])
        assert orch.board_caught_up is False
