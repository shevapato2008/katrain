import time
import pytest
from katrain.web.interface import WebKaTrain, NullEngine
from katrain.core.constants import MODE_PLAY


class MockEngine(NullEngine):
    def request_analysis(self, *args, **kwargs):
        pass


def test_timer_logic_parity():
    # Setup WebKaTrain with manual control
    katrain = WebKaTrain(force_package_config=True, enable_engine=False)
    katrain.engine = MockEngine()

    # Configure timer: 1 min main, 30s byoyomi, 5 periods
    katrain._config["timer"] = {"main_time": 1, "byo_length": 30, "byo_periods": 5, "minimal_use": 0, "sound": True}

    katrain._do_new_game(size=19)
    katrain.timer_paused = False
    # 这两条用例测的是**计时算术**,前提是「这一局已经开始走钟」。真实的一局由
    # 「棋盘可用」那一刻启动(实体盘=视觉绑定 / 无视觉部署=对局 WS 接上 / 屏幕降级=第一手),
    # 见 WebKaTrain.start_clock;起步闩本身由 test_clock_does_not_run_before_the_board_is_usable 守。
    katrain.start_clock()
    katrain.play_analyze_mode = MODE_PLAY
    # Ensure next player is human
    katrain.next_player_info.player_type = "player:human"

    # Reset baseline for test
    katrain.last_timer_update = time.time()

    # Initial state
    current_player = katrain.next_player_info.player
    assert katrain.main_time_used_by_player[current_player] == 0
    assert katrain.game.current_node.time_used == 0
    assert katrain.next_player_info.periods_used == 0

    # 1. Main time consumption
    katrain.last_timer_update = time.time() - 10  # 10 seconds ago
    katrain.update_timer()
    assert katrain.main_time_used_by_player[current_player] == pytest.approx(10, abs=0.1)
    assert katrain.game.current_node.time_used == 0

    # 2. Transition to Byoyomi (exhaust 60s main time)
    katrain.main_time_used_by_player[current_player] = 55
    katrain.last_timer_update = time.time() - 10  # 10 seconds ago (5s main, 5s byo)
    katrain.update_timer()

    assert katrain.main_time_used_by_player[current_player] == 60
    assert katrain.game.current_node.time_used == pytest.approx(5, abs=0.1)
    assert katrain.next_player_info.periods_used == 0

    # 3. Period decrement
    katrain.game.current_node.time_used = 25
    katrain.last_timer_update = time.time() - 10  # 10 seconds ago (5s left in period, 5s into next)
    katrain.update_timer()

    # After 35s total in byoyomi (25+10):
    # Period 1 (30s) consumed -> 1 period used
    # Remaining 5s in next period
    assert katrain.next_player_info.periods_used == 1
    assert katrain.game.current_node.time_used == pytest.approx(5, abs=0.1)

    # 4. Multiple periods at once
    katrain.game.current_node.time_used = 0
    katrain.last_timer_update = time.time() - 70  # 70 seconds ago (2 periods of 30s + 10s)
    katrain.update_timer()

    # 1 (prev) + 2 consumed = 3 periods used
    # 10s into the next period
    assert katrain.next_player_info.periods_used == 3
    assert katrain.game.current_node.time_used == pytest.approx(10, abs=0.1)


def test_timer_reset_on_move():
    katrain = WebKaTrain(force_package_config=True, enable_engine=False)
    katrain.engine = MockEngine()
    katrain._config["timer"] = {"main_time": 0, "byo_length": 30, "byo_periods": 5}
    katrain._do_new_game()
    katrain.timer_paused = False
    katrain.start_clock()
    katrain.play_analyze_mode = MODE_PLAY
    katrain.next_player_info.player_type = "player:human"

    # Reset baseline
    katrain.last_timer_update = time.time()

    # Consume some time
    katrain.last_timer_update = time.time() - 10
    katrain.update_timer()
    assert katrain.game.current_node.time_used == pytest.approx(10, abs=0.1)

    # Play a move (disable analysis to avoid background threads)
    katrain.game.play = lambda move, ignore_ko=False, analyze=False: super(type(katrain.game), katrain.game).play(
        move, ignore_ko=ignore_ko, analyze=False
    )
    katrain._do_play((3, 3))

    # New node should have 0 time used
    assert katrain.game.current_node.time_used == 0
    # last_timer_update should be reset to 'now'
    assert time.time() - katrain.last_timer_update < 0.5


def test_clock_does_not_run_before_the_board_is_usable():
    """建局那一刻 ≠ 能下第一手那一刻。

    RK3562 2026-09-20 实测:10:36:10 建局、10:37:19 视觉才绑上,中间 69 秒用户还在标定屏、
    碰不到棋盘,却已经被扣时(10:40 屏上实测 白方 4:37 剩余 vs 人类 0:36)。
    Fan 的裁定:「我要看到电子棋盘再开始计时」。
    """
    katrain = WebKaTrain(force_package_config=True, enable_engine=False)
    katrain.engine = MockEngine()
    katrain._do_new_game(size=19)
    # ⚠️ **不要写 `_config["timer"]`**。`force_package_config=True` 的实例最终会把配置存回
    # `~/.katrain/config.json`(用户真实配置),于是**下一次**跑测试时,早于本文件执行的
    # `tests/platforms/test_engine_manager.py::test_dump_engine_game_state_fixture`
    # 会把上一次留下的值读进签入的 fixture 里 —— 实测本文件原有两条就是这么把
    # `main_time` 在 0/1 之间来回推的。`active_game_timer` 是 `_do_new_game` 拷出来的
    # **每实例副本**(interface.py:813 `copy.deepcopy`),改它谁也影响不到。
    katrain.active_game_timer = {"main_time": 1, "byo_length": 30, "byo_periods": 5, "minimal_use": 0, "sound": True}
    katrain.timer_paused = False
    katrain.play_analyze_mode = MODE_PLAY
    katrain.next_player_info.player_type = "player:human"
    current_player = katrain.next_player_info.player

    # 起步之前:哪怕过了 69 秒,一秒都不记。
    assert katrain.clock_started is False
    katrain.last_timer_update = time.time() - 69
    katrain.update_timer()
    assert katrain.main_time_used_by_player[current_player] == 0
    assert katrain.game.current_node.time_used == 0

    # 起步是幂等的:第一次返回 True,之后都是 False(重连再绑不会把钟重置)。
    assert katrain.start_clock() is True
    assert katrain.start_clock() is False

    # 起步之后照常累计。
    katrain.last_timer_update = time.time() - 10
    katrain.update_timer()
    assert katrain.main_time_used_by_player[current_player] == pytest.approx(10, abs=0.1)


def test_clock_starts_on_the_first_move_when_nothing_else_started_it():
    """屏幕降级的局永远不会有视觉绑定 —— 没有这条兜底,钟永远不起步、超时永远不判。"""
    katrain = WebKaTrain(force_package_config=True, enable_engine=False)
    katrain.engine = MockEngine()
    katrain._do_new_game(size=19)
    katrain.active_game_timer = {"main_time": 1, "byo_length": 30, "byo_periods": 5, "minimal_use": 0, "sound": True}
    katrain.timer_paused = False
    katrain.play_analyze_mode = MODE_PLAY
    katrain.next_player_info.player_type = "player:human"
    assert katrain.clock_started is False

    katrain.game.play = lambda move, ignore_ko=False, analyze=False: super(type(katrain.game), katrain.game).play(
        move, ignore_ko=ignore_ko, analyze=False
    )
    katrain._do_play((3, 3))
    katrain.update_timer()
    assert katrain.clock_started is True


if __name__ == "__main__":
    test_timer_logic_parity()
    test_timer_reset_on_move()
    test_clock_does_not_run_before_the_board_is_usable()
    test_clock_starts_on_the_first_move_when_nothing_else_started_it()
    print("Tests passed!")
