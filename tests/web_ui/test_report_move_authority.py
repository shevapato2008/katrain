"""手数必须由服务端解析，客户端声明的 move_count 不作数。

回归的是一条实打实的白嫖路：UserGameCreate.move_count 由客户端提交
（user_games.py:32），声明 0 就会让预扣算出 0，而 cron 仍会跑满全盘。
"""
import pytest

from katrain.web.api.v1.endpoints import reports


SGF_3_MOVES = "(;GM[1]FF[4]SZ[19];B[pd];W[dp];B[pp])"
SGF_0_MOVES = "(;GM[1]FF[4]SZ[19])"


def test_counts_moves_from_sgf_not_from_client_claim():
    assert reports.count_moves(SGF_3_MOVES) == 3


def test_empty_game_counts_zero():
    assert reports.count_moves(SGF_0_MOVES) == 0


def test_malformed_sgf_raises_not_returns_zero():
    """解析不了必须报错。返回 0 等于把「读不懂」伪装成「不要钱」。"""
    with pytest.raises(ValueError):
        reports.count_moves("this is not sgf")


def test_none_or_blank_raises():
    with pytest.raises(ValueError):
        reports.count_moves("")
