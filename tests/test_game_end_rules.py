"""`katrain/web/core/game_end_rules.py` 的纯函数。

`is_awaiting_count` 在这里用假对象测条件组合；「真 WebKaTrain + 真 HTTP」那一侧在
`tests/test_local_play_game_end.py`。
"""

from types import SimpleNamespace

import pytest

from katrain.web.core.game_end_rules import is_awaiting_count, scaled_count_min_moves


@pytest.mark.parametrize(
    "base, size, expected",
    [
        (100, 19, 100),
        (100, 13, 47),
        (100, 9, 22),
        (10, 9, 2),  # 开发机 ~/.katrain/config.json 里真有 count_min_moves=10
        (0, 19, 1),  # 配置成 0 = 不设门槛；history 含根节点，恒 ≥ 1
    ],
)
def test_scaled_count_min_moves(base, size, expected):
    assert scaled_count_min_moves(base, size) == expected


def _node(is_pass, parent=None, end_state=None):
    return SimpleNamespace(is_pass=is_pass, parent=parent, end_state=end_state)


def _iface(*, suppress=True, game_type="pvp_local", current=None, manual_score=None):
    root = _node(None)  # 根节点没有着手：GameNode.is_pass 返回 None
    if current is None:
        current = _node(True, parent=_node(True, parent=root))
    game = SimpleNamespace(current_node=current, manual_score=manual_score)
    return SimpleNamespace(suppress_auto_eval=suppress, game_type=game_type, game=game)


@pytest.mark.parametrize("game_type", ["free", "pvp_local"])
def test_double_pass_in_board_mode_awaits_count(game_type):
    assert is_awaiting_count(_iface(game_type=game_type)) is True


def test_galaxy_never_awaits_count():
    assert is_awaiting_count(_iface(suppress=False)) is False


def test_missing_suppress_flag_counts_as_galaxy():
    iface = _iface()
    del iface.suppress_auto_eval
    assert is_awaiting_count(iface) is False


@pytest.mark.parametrize("game_type", ["ai_ladder_ranked", "rated", "ranked"])
def test_scoring_game_types_are_untouched(game_type):
    assert is_awaiting_count(_iface(game_type=game_type)) is False


def test_single_pass_after_a_stone_does_not_await():
    root = _node(None)
    current = _node(True, parent=_node(False, parent=root))
    assert is_awaiting_count(_iface(current=current)) is False


def test_pass_right_after_root_does_not_await():
    current = _node(True, parent=_node(None))
    assert is_awaiting_count(_iface(current=current)) is False


def test_root_node_does_not_await():
    assert is_awaiting_count(_iface(current=_node(None))) is False


@pytest.mark.parametrize("end_state", ["W+R", "B+T", "B+3.5"])
def test_a_real_result_ends_the_wait(end_state):
    root = _node(None)
    current = _node(True, parent=_node(True, parent=root), end_state=end_state)
    assert is_awaiting_count(_iface(current=current)) is False


def test_arrived_analysis_does_not_end_the_wait():
    """变异闸：把 `game.manual_score` 加回条件，这一格必须红。

    manual_score 是由 `current_node.score` 现算的估计，分析一回来就是 "黑+3.0?" 这种串；
    而数子恰恰要等这份分析。它若是条件，自动数子永远在「分析到了」那一刻被判成已终局。
    """
    assert is_awaiting_count(_iface(manual_score="黑+3.0?")) is True


def test_no_game_does_not_await():
    iface = _iface()
    iface.game = None
    assert is_awaiting_count(iface) is False
