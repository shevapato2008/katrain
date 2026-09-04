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


def test_web_and_cron_parsers_agree_on_every_real_sgf():
    """web 与 cron 是**两套**解析器，截断依赖它们数出同一个数。

    `katrain/web/api/v1/endpoints/reports.py:count_moves` 用
    `katrain.core.sgf_parser`；`katrain/cron/jobs/report_analyze.py` 用
    `katrain.cron.sgf.parse_game`。cron 会把分析截断到 `moves[:task.total_moves]`，
    而 total_moves 是 web 数的 —— 两边不一致时，**多出来的那几手会被静默丢掉**，
    用户拿到一份短一截的报告却看不出哪里少了。

    这条曾经真的红过：`xmgt97.sgf` 把第一手 `Black[ff]` 和 SZ/KM 一起放在**根节点**里，
    而 count_moves 原来先 `node = node.children[0]` 再判断、从不看根节点自己的 move
    ⇒ web 数 59、cron 数 60。合成 SGF 的根节点没有 move，所以单测覆盖不到。
    """
    import glob
    import os

    from katrain.cron.sgf import parse_game

    root_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    files = sorted(glob.glob(os.path.join(root_dir, "*.sgf")))
    assert files, "tests/data 下没有 SGF —— 这条闸会变成空转，必须查"

    mismatches = []
    compared = 0
    for path in files:
        with open(path, encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        # 只吞「这份棋谱解析不了」，**不吞脚手架自己的错误**。
        # 第一版这里写的是宽泛的 `except Exception: continue`，把
        # `count_moves` 拼错导致的 NameError 也当成「跳过这份棋谱」吞掉了 ——
        # 于是每份都跳过、mismatches 恒空、闸永远绿。变异验证当场把它抓了出来。
        try:
            web_n = reports.count_moves(content)
        except ValueError:
            continue
        try:
            cron_n = len(parse_game(content).moves)
        except (ValueError, IndexError, KeyError):
            continue
        compared += 1
        if web_n != cron_n:
            mismatches.append((os.path.basename(path), web_n, cron_n))

    assert compared >= 5, (
        f"只比对了 {compared} 份棋谱 —— 少于预期，说明大多数被跳过了，"
        "这条闸正在空转"
    )
    assert mismatches == [], (
        "web 与 cron 数出的手数不一致，cron 的截断会静默丢手："
        + "; ".join(f"{n}: web={w} cron={c}" for n, w, c in mismatches)
    )
