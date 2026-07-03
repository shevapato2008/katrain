"""Orchestrator: game state + observed board -> LED writes, catch-up gate, reminder."""

import asyncio
import time

import numpy as np
import pytest

from katrain.web.core.physical_play import PhysicalPlayConfig
from katrain.web.core.physical_play_orchestrator import PhysicalPlayOrchestrator


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
