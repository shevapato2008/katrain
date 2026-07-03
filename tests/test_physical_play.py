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

    def test_lamp_never_relights_after_observed(self, planner):
        # 弱光抖动修复：目标点一旦观测到已摆放，之后视觉丢帧不得重亮灯——
        # 否则红灯在黑子下点亮，红光泄漏又让模型把黑子读成 led_red，形成死循环。
        # 真消失由 sync missing_anomaly → mismatch 对话框（独立通路）兜底。
        expected = board([(3, 3, BLACK)])
        planner.on_expected(expected)
        assert planner.tick(expected, board([(3, 3, BLACK)])).points == []  # 已观测到
        plan = planner.tick(expected, board())  # 视觉抖动丢失该子
        assert plan.points == []
        assert plan.caught_up is True

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


class TestGuidanceScope:
    """己方棋子 LED 零输出：placement 灯只为 AI 颜色（guided_colors）+ 让子（setup_cells）亮。"""

    def test_human_stone_never_lights(self, planner):
        # 用户执黑（AI 执白）：黑子缺失——无论从未观测还是抖动——都不亮灯。
        planner.set_context(guided_colors={WHITE}, setup_cells=set())
        expected = board([(3, 3, BLACK)])
        planner.on_expected(expected)
        plan = planner.tick(expected, board())
        assert plan.points == []
        assert plan.caught_up is True  # 己方子缺失不算「落后」→ 不触发提醒/暂停

    def test_ai_stone_lights_until_placed_then_flicker_immune(self, planner):
        planner.set_context(guided_colors={WHITE}, setup_cells=set())
        expected = board([(5, 5, WHITE)])
        planner.on_expected(expected)
        assert planner.tick(expected, board()).points == [{"row": 5, "col": 5, "color": "white"}]
        assert planner.tick(expected, expected).points == []  # 摆好 → 灭
        assert planner.tick(expected, board()).points == []  # 之后抖动 → 不复亮

    def test_setup_cells_guided_regardless_of_color(self, planner):
        # 让 2 子：黑子（人类颜色）但属 root 布子 → 红灯全亮、逐摆逐灭。
        planner.set_context(guided_colors={WHITE}, setup_cells={(3, 3), (15, 15)})
        expected = board([(3, 3, BLACK), (15, 15, BLACK)])
        planner.on_expected(expected)
        plan = planner.tick(expected, board())
        assert {(p["row"], p["col"]) for p in plan.points} == {(3, 3), (15, 15)}
        plan = planner.tick(expected, board([(3, 3, BLACK)]))  # 摆了一颗
        assert {(p["row"], p["col"]) for p in plan.points} == {(15, 15)}

    def test_new_expected_stone_rearms_guidance_after_capture(self, planner):
        # AI 白子被提掉又在同格重新落子：EMPTY→stone 跃迁清除观测记忆 → 重新引导。
        planner.set_context(guided_colors={WHITE}, setup_cells=set())
        b1 = board([(5, 5, WHITE)])
        planner.on_expected(b1)
        planner.tick(b1, b1)  # 观测到 → 记忆
        planner.on_expected(board())  # 提掉
        planner.tick(board(), board())  # 物理拿除完成
        planner.on_expected(b1)  # 同格重新落子
        plan = planner.tick(b1, board())
        assert plan.points == [{"row": 5, "col": 5, "color": "white"}]

    def test_no_context_keeps_legacy_all_color_guidance(self, planner):
        # 未提供玩家信息（双人局识别不全等）→ 兜底：所有颜色都引导（旧行为）。
        expected = board([(3, 3, BLACK)])
        planner.on_expected(expected)
        assert planner.tick(expected, board()).points == [{"row": 3, "col": 3, "color": "black"}]

    def test_both_human_colors_no_lamps(self, planner):
        # 双人本地对弈：双方都是人 → guided_colors 空集 → 全程无 placement 灯。
        planner.set_context(guided_colors=set(), setup_cells=set())
        expected = board([(3, 3, BLACK), (5, 5, WHITE)])
        planner.on_expected(expected)
        plan = planner.tick(expected, board())
        assert plan.points == []
        assert plan.caught_up is True


class TestExtrasVsPendingMove:
    """回归（首手落子不识别）：单颗己方颜色的多余子 = 正在确认中的落子，绝不能点
    蓝色清理灯——那盏灯的格子曾被 vision 遮蔽，形成 灯亮→识别丢失→灯灭→识别恢复 的
    死循环，让开局第一手永远无法注册。"""

    def test_single_human_extra_never_gets_cleanup_lamp(self, planner):
        planner.set_context(guided_colors={WHITE}, setup_cells=set())  # 用户执黑
        empty = board()
        planner.on_expected(empty)
        pending_move = board([(3, 3, BLACK)])  # 用户刚落的黑子，尚未确认
        for _ in range(10):  # 远超 debounce 阈值
            plan = planner.tick(empty, pending_move)
        assert plan.points == []

    def test_single_ai_color_extra_still_lamps(self, planner):
        planner.set_context(guided_colors={WHITE}, setup_cells=set())
        empty = board()
        planner.on_expected(empty)
        stray_white = board([(9, 9, WHITE)])  # 白=AI 色，人不会替 AI 落子 -> 真残子
        for _ in range(3):
            plan = planner.tick(empty, stray_white)
        assert {"row": 9, "col": 9, "color": "remove"} in plan.points

    def test_multiple_human_extras_still_lamp(self, planner):
        planner.set_context(guided_colors={WHITE}, setup_cells=set())
        empty = board()
        planner.on_expected(empty)
        pile = board([(9, 9, BLACK), (10, 10, BLACK)])  # 一堆残子 = 真清理场景
        for _ in range(3):
            plan = planner.tick(empty, pile)
        assert len(plan.points) == 2

    def test_no_context_keeps_legacy_lamping(self, planner):
        empty = board()
        planner.on_expected(empty)
        stray = board([(9, 9, BLACK)])
        for _ in range(3):
            plan = planner.tick(empty, stray)
        assert plan.points == [{"row": 9, "col": 9, "color": "remove"}]

    def test_both_human_single_extra_never_lamps(self, planner):
        planner.set_context(guided_colors=set(), setup_cells=set())  # 双人对弈
        empty = board()
        planner.on_expected(empty)
        for _ in range(10):
            plan = planner.tick(empty, board([(9, 9, WHITE)]))
        assert plan.points == []


class TestExtrasExclusionDecay:
    """裁决 REAL 的边界：清理堆缩到一颗时，幸存残子已过防抖计数——保持点灯，
    不得突然被豁免（灯灭 + 被当成落子注入）。"""

    def test_pile_survivor_keeps_its_lamp(self, planner):
        planner.set_context(guided_colors={WHITE}, setup_cells=set())
        empty = board()
        planner.on_expected(empty)
        pile = board([(9, 9, BLACK), (10, 10, BLACK)])
        for _ in range(3):  # both cross the 2-tick debounce
            plan = planner.tick(empty, pile)
        assert len(plan.points) == 2
        survivor = board([(9, 9, BLACK)])  # user removed one
        plan = planner.tick(empty, survivor)
        assert plan.points == [{"row": 9, "col": 9, "color": "remove"}]  # lamp stays

    def test_fresh_single_stone_still_exempt(self, planner):
        planner.set_context(guided_colors={WHITE}, setup_cells=set())
        empty = board()
        planner.on_expected(empty)
        for _ in range(10):
            plan = planner.tick(empty, board([(3, 3, BLACK)]))  # never lamped before
        assert plan.points == []
