"""LedPlanner: LED batch = f(expected digital board, observed physical board)."""

import numpy as np
import pytest

from katrain.web.core.physical_play import BLACK, EMPTY, WHITE, LedPlanner, PhysicalPlayConfig


def board(stones=()):
    b = np.zeros((19, 19), dtype=int)
    for r, c, v in stones:
        b[r][c] = v
    return b


@pytest.fixture
def planner():
    return LedPlanner(PhysicalPlayConfig(extra_stone_debounce_ticks=2))


class TestPlacementLamps:
    def test_ai_move_lights_stone_color_until_placed(self, planner):
        expected = board([(3, 3, BLACK)])  # AI(黑) 已在数字盘落子
        planner.on_expected(expected)
        plan = planner.tick(expected, board())  # 物理盘还没摆
        assert plan.points == [{"row": 3, "col": 3, "color": "black"}]  # 黑→红灯
        assert plan.caught_up is False
        plan = planner.tick(expected, expected)  # 用户替 AI 摆好
        assert plan.points == [] and plan.caught_up is True  # 灯灭

    def test_any_stone_on_target_extinguishes_lamp(self, planner):
        # 评审 E（眩光）：目标点一出现任何棋子检测，灯立即灭——即便颜色不对。
        # 错色子由 sync 异常流（Task 5 unexpected 分支）弹对话框，不用常亮灯引导。
        expected = board([(3, 3, WHITE)])
        planner.on_expected(expected)
        plan = planner.tick(expected, board([(3, 3, BLACK)]))  # 错色也算「有子」
        assert plan.points == []
        assert plan.caught_up is True

    def test_lamp_relights_when_detection_vanishes(self, planner):
        # 眩光误检消失 → 目标点重新读空 → 灯下一 tick 回亮
        expected = board([(3, 3, BLACK)])
        planner.on_expected(expected)
        assert planner.tick(expected, board([(3, 3, BLACK)])).points == []  # 检测到了（或眩光）
        plan = planner.tick(expected, board())  # 检测消失
        assert plan.points == [{"row": 3, "col": 3, "color": "black"}]
        assert plan.caught_up is False

    def test_handicap_stones_all_lit(self, planner):
        expected = board([(3, 3, BLACK), (15, 15, BLACK)])
        planner.on_expected(expected)
        plan = planner.tick(expected, board())
        assert {(p["row"], p["col"]) for p in plan.points} == {(3, 3), (15, 15)}
        assert all(p["color"] == "black" for p in plan.points)


class TestRemovalLamps:
    def test_digital_capture_blue_until_physically_removed(self, planner):
        before = board([(5, 5, WHITE), (3, 3, BLACK)])
        after = board([(3, 3, BLACK)])  # 数字盘提掉 (5,5)
        planner.on_expected(before)
        planner.on_expected(after)
        plan = planner.tick(after, before)  # 物理盘白子还在
        assert {"row": 5, "col": 5, "color": "remove"} in plan.points
        assert plan.caught_up is False
        plan = planner.tick(after, after)  # 拿掉后
        assert plan.points == [] and plan.caught_up is True

    def test_undo_then_redo_cancels_removal(self, planner):
        b1 = board([(3, 3, BLACK)])
        planner.on_expected(b1)
        planner.on_expected(board())  # 悔棋：期望盘失去 (3,3) → 待提
        planner.on_expected(b1)  # 重做：期望盘又有 → 取消待提
        plan = planner.tick(b1, b1)
        assert plan.points == [] and plan.caught_up is True


class TestExtraStones:
    def test_leftover_stone_debounces_to_blue(self, planner):
        empty = board()
        planner.on_expected(empty)
        extra = board([(9, 9, BLACK)])  # 开局残子
        plan = planner.tick(empty, extra)  # 第 1 tick：不点灯（防抖）
        assert plan.points == []
        plan = planner.tick(empty, extra)  # 第 2 tick（=debounce 阈值）：蓝灯
        assert plan.points == [{"row": 9, "col": 9, "color": "remove"}]
        assert plan.caught_up is True  # 残子不阻塞落子注入（Q4 门只看 place/remove-pending）

    def test_extras_not_flagged_while_placement_pending(self, planner):
        # Q4 重设计：AI 子未摆好（to_place 非空）期间，用户抢下的子绝不能被蓝灯
        # 误导为「请拿走」——extras 防抖在 to_place 非空时整体挂起、计数清零。
        expected = board([(3, 3, BLACK)])  # AI 落子待摆
        planner.on_expected(expected)
        premature = board([(9, 9, WHITE)])  # 用户抢下自己的一手（AI 子还没摆）
        for _ in range(5):
            plan = planner.tick(expected, premature)
        assert {"row": 9, "col": 9, "color": "remove"} not in plan.points
        assert plan.points == [{"row": 3, "col": 3, "color": "black"}]  # 只有 AI 落子灯


class TestMixedBatch:
    def test_ai_move_and_capture_one_batch(self, planner):
        before = board([(5, 5, WHITE)])
        after = board([(3, 3, BLACK)])  # AI 落子 + 提掉 (5,5)
        planner.on_expected(before)
        planner.on_expected(after)
        plan = planner.tick(after, before)
        assert {"row": 3, "col": 3, "color": "black"} in plan.points
        assert {"row": 5, "col": 5, "color": "remove"} in plan.points
