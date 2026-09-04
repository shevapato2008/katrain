# tests/web_ui/test_analysis_cost.py
"""算力计价：按 moves × visits 算，不按盘算。"""
import pytest

from katrain.web.core import analysis_cost as ac


def test_cost_scales_with_move_count():
    """100 手认输的棋不应该和 300 手收一样的钱 —— 这是本功能存在的理由。"""
    short = ac.report_cost(100, 500)
    long = ac.report_cost(300, 500)
    assert long == pytest.approx(short * 3, rel=0.01)
    assert short < long


def test_cost_scales_with_visits():
    assert ac.report_cost(200, 2000) == 4 * ac.report_cost(200, 500)


def test_standard_250_move_report():
    # 250 手 × 500 visits = 125_000 visits = 125 credits
    assert ac.report_cost(250, 500) == 125


def test_zero_moves_costs_nothing():
    assert ac.report_cost(0, 500) == 0


def test_tiny_game_still_costs_at_least_one():
    assert ac.report_cost(1, 1) == 1


def test_model_factor_applied():
    assert ac.report_cost(250, 500, "b18") < ac.report_cost(250, 500, "b28")


def test_unknown_model_falls_back_to_one():
    assert ac.report_cost(250, 500, "no-such-net") == ac.report_cost(250, 500, "b28")


def test_negative_moves_rejected():
    with pytest.raises(ValueError):
        ac.report_cost(-1, 500)
