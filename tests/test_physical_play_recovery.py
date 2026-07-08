"""Manual recovery from a stuck removal / mismatch_warning deadlock.

Regression for the kiosk bug: mid-game a blue "remove" LED lit, then BLACK moves
stopped registering and "确认中" hung. Root cause (workflow wjwvya7r3): an
un-clearable removal — a physical stone the camera keeps seeing at a captured/undone
point (LED glare / white false-negative) — latched `_removal_pending`, so
`caught_up=False` -> move detection paused forever, with no user-reachable escape.

`LedPlanner.reconcile` drops that stuck removal (it degrades to a non-blocking
cleanup extra); `Orchestrator.resync` re-baselines vision to the digital board and
releases the pause; the `/sync/reset` endpoint drives resync so the always-visible
kiosk "重置识别" button (and the existing escalation dialog) recover the game.
"""

import numpy as np
import pytest

from katrain.vision.sync import game_state_stones_to_board
from katrain.web.core.physical_play import BLACK, WHITE, LedPlanner, PhysicalPlayConfig
from katrain.web.core.physical_play_orchestrator import PhysicalPlayOrchestrator


def board(stones=()):
    b = np.zeros((19, 19), dtype=int)
    for r, c, v in stones:
        b[r][c] = v
    return b


# -- LedPlanner.reconcile ----------------------------------------------------


@pytest.fixture
def planner():
    return LedPlanner(PhysicalPlayConfig(extra_stone_debounce_ticks=2))


def test_reconcile_makes_stuck_removal_stop_gating(planner):
    before = board([(5, 5, WHITE), (3, 3, BLACK)])
    after = board([(3, 3, BLACK)])  # 数字盘提掉 (5,5)
    planner.on_expected(before)
    planner.on_expected(after)
    stuck = board([(5, 5, WHITE), (3, 3, BLACK)])  # 物理白子拿不掉(眩光/漏检)
    assert planner.tick(after, stuck).caught_up is False  # removal 卡住 gate

    planner.reconcile(after)  # 手动恢复：以数字盘为准
    plan = planner.tick(after, stuck)
    assert plan.caught_up is True  # 不再 gate（白子降级为非阻塞清理 extra）


def test_reconcile_preserves_already_placed_tracking(planner):
    expected = board([(3, 3, BLACK)])
    planner.on_expected(expected)
    planner.tick(expected, expected)  # 观测到已摆放 -> _observed_once
    planner.reconcile(expected)
    plan = planner.tick(expected, board())  # 视觉抖动丢帧
    assert plan.points == []  # 不重亮 to_place（保留 _observed_once）
    assert plan.caught_up is True


def test_reconcile_single_human_capture_still_lamps(planner):
    # Human=黑, AI=白 (guided_colors={WHITE}). AI 提掉人类唯一一颗黑子——最常见的单子提子。
    # reconcile 后这颗仍在物理盘上的黑子若掉进"单颗人类色=落子进行中"豁免，就会被永久
    # 熄灯（拿除引导消失，棋盘悄悄失同步）。修复：reconcile 把 removal 越过 debounce 播种，
    # 使其首个 tick 就以蓝色清理灯出现（非阻塞）。
    planner.set_context(guided_colors={WHITE}, setup_cells=set())
    before = board([(3, 3, BLACK)])
    after = board()  # AI 提子：数字盘失去黑(3,3)
    planner.on_expected(before)
    planner.on_expected(after)
    stuck = board([(3, 3, BLACK)])  # 物理黑子还在
    assert planner.tick(after, stuck).caught_up is False  # reconcile 前 removal 卡 gate

    planner.reconcile(after)
    plan = planner.tick(after, stuck)
    assert {"row": 3, "col": 3, "color": "remove"} in plan.points  # 首 tick 就亮蓝灯
    assert plan.caught_up is True  # 但非阻塞（不再冻结对局）


# -- Orchestrator.resync -----------------------------------------------------


class FakeLed:
    def __init__(self):
        self.calls = []

    def set_points(self, points, *, strict=False):
        self.calls.append(("set_points", points))
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
        self.reset_calls = 0
        self.reset_expected = None

    def get_detected_board(self):
        return self.detected

    def set_expected_from_stones(self, stones, board_size=19):
        self.expected_pushes.append(stones)

    def reset_sync(self, expected=None):
        self.reset_calls += 1
        self.reset_expected = expected

    def pause_detection(self):
        self.paused = True

    def resume_detection(self):
        self.paused = False

    def set_lit_points(self, points):
        self.lit = points


class FakeManager:
    def broadcast_to_session(self, sid, payload):
        pass


def _orch(**cfg):
    orch = PhysicalPlayOrchestrator(
        config=PhysicalPlayConfig(**cfg),
        led=FakeLed(),
        vision=FakeVision(),
        session_manager=FakeManager(),
        touch_led_activity=lambda: None,
        clock=lambda: 0.0,
    )
    orch._session_id = "s1"  # bypass on_bind (needs a running loop + real session)
    return orch, orch._vision


def _state(stones, end_result=None):
    return {"stones": stones, "board_size": [19, 19], "end_result": end_result}


def test_resync_releases_stuck_pause_and_repushes_digital():
    orch, vision = _orch(extra_stone_debounce_ticks=99)  # keep the extra from re-lamping mid-test
    white_and_black = [["W", [5, 5], None, 1], ["B", [3, 3], None, 2]]
    orch.on_game_state(_state(white_and_black))
    vision.detected = game_state_stones_to_board(white_and_black, 19).tolist()  # physical == digital
    orch._tick_once()
    assert orch.board_caught_up is True

    black_only = [["B", [3, 3], None, 2]]  # 数字盘提掉白子，物理白子还在（拿不掉）
    orch.on_game_state(_state(black_only))
    orch._tick_once()
    assert orch.board_caught_up is False  # removal gate
    assert vision.paused is True  # -> 落子识别被暂停（黑棋卡死的机制）

    orch.resync()  # 兜底恢复
    assert orch.board_caught_up is True  # 暂停解除
    assert vision.paused is False
    assert vision.reset_calls == 1  # 单条原子命令（sync→数字盘，检测器→并集）
    assert vision.reset_expected is not None  # 数字盘作为权威随命令下发（丢弃相机幻影）


def test_resync_without_bound_state_is_safe():
    orch, vision = _orch()
    orch._latest_state = None
    orch.resync()  # 不崩，退化为 vision.reset_sync
    assert vision.reset_calls == 1
