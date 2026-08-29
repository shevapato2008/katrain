"""报告管线的 SGF 解析。

这里每条用例都对应一个曾经真实存在的缺陷（旧的正则解析器）：
让子石被丢、分支被拍平、旧式停一手变成盘外坐标、注释里的假着法被当真。
变异记录：把 `_parse_sgf` 换回 `re.findall(r";([BW])\\[([a-z]{0,2})\\]", sgf)`
并硬写 initial_stones=[] / initial_player="B"，本文件 5 条用例会红（实测）。
"""

import pytest

from katrain.cron.jobs.report_analyze import _parse_sgf

HANDICAP = "(;GM[1]FF[4]SZ[19]HA[4]KM[0.5]AB[dd][pd][dp][pp];W[qf];B[nc])"
BRANCHED = "(;SZ[19];B[pd];W[dp](;B[qp];W[dc])(;B[dc];W[qp]))"
COMMENTED = "(;SZ[19];B[pd]C[try ;W[qq\\] here];W[dp])"   # SGF 里 ] 必须转义


def test_handicap_stones_reach_the_engine():
    _, _, _, moves, initial_stones, initial_player = _parse_sgf(HANDICAP)
    assert len(initial_stones) == 4
    assert all(p == "B" for p, _ in initial_stones)
    assert sorted(c for _, c in initial_stones) == ["D16", "D4", "Q16", "Q4"]
    # 让子局白先。写死 "B" 会让白棋每一手都被算成灾难。
    assert initial_player == "W"
    assert moves == [("W", "R14"), ("B", "O17")]


def test_handicap_stones_are_not_replayed_as_moves():
    """摆子不能同时出现在 initial_stones 和 moves 里，否则手数全错位。"""
    _, _, _, moves, initial_stones, _ = _parse_sgf(HANDICAP)
    move_coords = {c for _, c in moves}
    assert not move_coords & {c for _, c in initial_stones}


def test_variations_do_not_leak_into_the_mainline():
    _, _, _, moves, _, _ = _parse_sgf(BRANCHED)
    assert moves == [("B", "Q16"), ("W", "D4"), ("B", "R4"), ("W", "D17")]
    # 旧解析器会得到 6 手，含两次非法重复落子
    assert len(moves) == 4
    assert len(moves) == len(set(moves))


def test_a_move_inside_a_comment_is_not_a_move():
    _, _, _, moves, _, _ = _parse_sgf(COMMENTED)
    assert moves == [("B", "Q16"), ("W", "D4")]


def test_malformed_sgf_raises_instead_of_producing_garbage_moves():
    """真解析器会抛，旧正则会静默返回垃圾着法。

    调用方 _process_task 捕获它并把任务标 failed —— 见同文件的 try/except。
    """
    from katrain.core.sgf_parser import ParseError

    with pytest.raises(ParseError):
        _parse_sgf("(;SZ[19];B[pd]C[unescaped ] bracket];W[dp])")


@pytest.mark.parametrize("sgf,expected", [
    ("(;SZ[19];B[pd];W[];B[dp])", "pass"),          # FF[4] 空着 = 停一手
    ("(;SZ[19];B[pd];W[tt];B[dp])", "pass"),        # FF[3] 老式停一手
])
def test_passes_become_pass_not_an_off_board_coordinate(sgf, expected):
    """旧解析器把 ;W[tt] 转成 'U0'，KataGo 报错 → 3 次重试 → 整个任务失败。"""
    _, _, _, moves, _, _ = _parse_sgf(sgf)
    assert moves[1] == ("W", expected)


def test_plain_even_game_is_unchanged():
    """绿分支也要跑到：普通分先局不该受这些修复影响。"""
    bs, komi, rules, moves, initial_stones, initial_player = _parse_sgf(
        "(;GM[1]FF[4]SZ[19]KM[7.5]RU[Chinese];B[pd];W[dp];B[qp])"
    )
    assert bs == 19
    assert komi == pytest.approx(7.5)
    assert rules == "chinese"
    assert initial_stones == []
    assert initial_player == "B"
    assert moves == [("B", "Q16"), ("W", "D4"), ("B", "R4")]


def test_explicit_PL_wins_over_the_handicap_heuristic():
    _, _, _, _, _, initial_player = _parse_sgf("(;SZ[19]AB[dd][pd]PL[B];B[qp])")
    assert initial_player == "B"
