"""`katrain/cron/sgf.py` —— 复盘报告的 SGF 解析。

这里每一条都对着**原来那条平铺正则**（`re.findall(r";([BW])\\[…\\]")` 扫全文）
真的会算错的一种谱。它们的共同点是**屏上看不出来**：报告照样跑完、照样有胜率曲线，
只是那条曲线算的不是这盘棋。

历史行为（`git show 6056320e:katrain/cron/jobs/report_analyze.py`）：
分支谱的变化图被拼进主线 · `AB[]/AW[]` 一个都不读且调用处写死 `initial_stones=[]`
⇒ 让子局从空盘算 · 注释里的 `;B[…]` 文本变成幽灵着手 · `[tt]` 变成 `U0` 这种不存在的点。
"""

import pytest

from katrain.cron.sgf import parse_game, sgf_to_gtp


class TestMainLineOnly:
    def test_变化图不进主线(self):
        # 第一个子树是主线的延续；后面那些是变化图，整棵跳过。
        game = parse_game("(;FF[4]SZ[19];B[pd];W[dd](;B[qq])(;B[cc];W[dq]))")
        assert game.moves == [("B", "Q16"), ("W", "D16"), ("B", "R3")]

    def test_嵌套变化图也跳干净(self):
        game = parse_game("(;FF[4]SZ[19];B[pd](;W[dd](;B[qq])(;B[cc]))(;W[cc];B[dq]))")
        assert game.moves == [("B", "Q16"), ("W", "D16"), ("B", "R3")]

    def test_一个文件里的第二盘棋不混进来(self):
        game = parse_game("(;FF[4]SZ[19];B[pd])(;FF[4]SZ[19];B[dd])")
        assert game.moves == [("B", "Q16")]

    def test_注释里的着手文本不是着手(self):
        # SGF 里值内的 `]` 要转义、`[` 不用 —— 按规则读就不会把正文当成节点。
        game = parse_game("(;FF[4]SZ[19]C[这里该走 ;B[aa\\] 才对];B[pd])")
        assert game.moves == [("B", "Q16")]

    def test_主线深到几百手也不炸(self):
        # 每手都挂一个变化图的谱：主线嵌 400 层，每层还挂一个要跳过的兄弟变化图。
        # 解析是迭代的，不吃递归上限。
        nested = ""
        for _ in range(400):
            nested = "(;B[aa]" + nested + "(;W[dd])" + ")"
        game = parse_game("(;FF[4]SZ[19]" + nested + ")")
        # 最里面那层没有更深的孩子，于是它的第一个子树就是那个 W —— 主线到此为止。
        assert [color for color, _ in game.moves] == ["B"] * 400 + ["W"]


class TestSetupStones:
    def test_让子局的摆子走_initial_stones_而不是消失(self):
        game = parse_game("(;FF[4]SZ[19]HA[2]AB[dd][pp];W[qq])")
        assert game.initial_stones == [["B", "D16"], ["B", "Q4"]]
        assert game.handicap == 2
        assert game.moves == [("W", "R3")]

    def test_让子局第一手是白_没有落子时也判得出来(self):
        game = parse_game("(;FF[4]SZ[19]HA[2]AB[dd][pp])")
        assert game.initial_player == "W"

    def test_摆好的局面_黑白都有(self):
        game = parse_game("(;FF[4]SZ[19]AB[dd]AW[pp];B[qq])")
        assert game.initial_stones == [["B", "D16"], ["W", "Q4"]]
        assert game.initial_player == "B"

    def test_AE_把摆上的子拿掉(self):
        game = parse_game("(;FF[4]SZ[19]AB[dd][pp];AE[dd];B[qq])")
        assert game.initial_stones == [["B", "Q4"]]

    def test_PL_说了算(self):
        game = parse_game("(;FF[4]SZ[19]AB[dd]PL[B];B[qq])")
        assert game.initial_player == "B"

    def test_第一手之后的摆子表达不了_丢掉但要留声(self):
        # KataGo 的 initialStones 只描述开局前的局面；中盘摆子没地方放。
        # 丢是没办法，**丢得无声无息**才是问题。
        game = parse_game("(;FF[4]SZ[19];B[pd];W[dd];AB[qq][cc])")
        assert game.initial_stones == []
        assert game.dropped_midgame_setup == 2
        assert game.moves == [("B", "Q16"), ("W", "D16")]

    def test_摆子不算进手数(self):
        game = parse_game("(;FF[4]SZ[19]HA[4]AB[dd][pd][dp][pp];W[qq];B[cc])")
        assert len(game.moves) == 2


class TestCoordinates:
    @pytest.mark.parametrize(
        "sgf_coord,expected",
        [
            ("dd", "D16"),  # 左上星位
            ("pd", "Q16"),
            ("pp", "Q4"),
            ("jj", "K10"),  # 天元：SGF 第 10 列是 j，GTP 跳过 I ⇒ K
            ("ia", "J19"),  # SGF 的 i 就是 GTP 的 J
            ("aa", "A19"),
            ("ss", "T1"),
        ],
    )
    def test_十九路坐标(self, sgf_coord, expected):
        assert sgf_to_gtp(sgf_coord, 19) == expected

    def test_空值是虚手(self):
        assert sgf_to_gtp("", 19) == "pass"

    def test_tt_在十九路以内是老写法的虚手(self):
        # 原来这里算出 "U0" —— 既不在盘上也不是虚手，直接喂给了引擎。
        assert sgf_to_gtp("tt", 19) == "pass"
        assert sgf_to_gtp("tt", 9) == "pass"

    def test_盘外的坐标读不懂就说读不懂(self):
        # 返回 None 让调用方跳过。编一个坐标出来比少一手更坏。
        assert sgf_to_gtp("zz", 19) is None
        assert sgf_to_gtp("tt", 21) == "U2"  # 21 路上 tt 是真的一点(GTP 跳 I ⇒ 第 20 列是 U)
        assert sgf_to_gtp("d", 19) is None

    def test_九路上十九路的坐标算越界(self):
        assert sgf_to_gtp("dd", 9) == "D6"
        assert sgf_to_gtp("pp", 9) is None

    def test_读不懂的那手跳过_其余照常(self):
        game = parse_game("(;FF[4]SZ[19];B[pd];W[zz];B[dd])")
        assert game.moves == [("B", "Q16"), ("B", "D16")]

    def test_虚手在主线里保留(self):
        game = parse_game("(;FF[4]SZ[19];B[pd];W[];B[tt])")
        assert game.moves == [("B", "Q16"), ("W", "pass"), ("B", "pass")]


class TestRootProperties:
    def test_棋盘规则贴目(self):
        game = parse_game("(;FF[4]SZ[9]KM[6.5]RU[Japanese];B[ee])")
        assert (game.board_size, game.komi, game.rules) == (9, 6.5, "japanese")
        assert game.moves == [("B", "E5")]

    def test_长写法的棋盘尺寸(self):
        assert parse_game("(;FF[4]SZ[19:19];B[pd])").board_size == 19

    def test_读得到胜负(self):
        assert parse_game("(;FF[4]SZ[19]RE[B+2.5];B[pd])").result == "B+2.5"

    def test_缺项走默认值(self):
        game = parse_game("(;FF[4];B[pd])")
        assert (game.board_size, game.komi, game.rules, game.result) == (19, 7.5, "chinese", None)

    def test_坏值不炸_退回默认(self):
        game = parse_game("(;FF[4]SZ[19]KM[没写]HA[x];B[pd])")
        assert game.komi == 7.5
        assert game.handicap == 0

    def test_空谱(self):
        for junk in ("", "()", "不是棋谱"):
            game = parse_game(junk)
            assert game.moves == []
            assert game.initial_stones == []
