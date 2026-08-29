"""`get_state()["history"]` 每一行带上着法坐标(`move` / `player`)。

围棋 kiosk 星阵屏(屏 10)要在右栏画一份棋谱,而在此之前**前端拼不出来**:

* `history` 只有 `node_id` / `score` / `winrate` —— **没有坐标**;
* `stones` 虽然带 `move_number`,却是**当前盘面**,`_calculate_groups()` 已经把被提掉的子
  拿走了 —— 拿它拼谱会缺手,而且缺的正是最该看见的那几手。

`interface.py` 的 `get_state()` 里本来就有一个遍历主线每个 `GameNode` 的循环
(`path_to_root + continuation`),坐标就在 `node.move` 上,顺手写进去即可。

这份测试守三件事,第三件是**这次改动的全部理由**:
  1. 口径:`history[0]` 是根节点,没有着法;第 n 手落在 `history[n]`;`Move.gtp()` 的写法。
  2. 虚手是 `"pass"`,不是 `None` —— `None` 和「根节点」撞车,前端分不出「这一手是虚手」
     和「这一格没有着法」。
  3. **被提掉的子仍在 `history` 里,而 `stones` 里没有。**

用真的 `SessionManager -> WebKaTrain` 栈(不 mock),同 `tests/platforms/` 那几份。
⚠️ **不能放 `tests/web_ui/`**:那个目录的 `conftest.py` 把 `WebKaTrain` 整个 mock 掉了,
`get_state()["history"][n]["move"]` 会拿到一个 `MagicMock` —— 断言写什么都过不了,
而「过不了」还不是最坏的:改成宽松一点就会**永远绿**,而它一行真代码都没执行。
"""

from __future__ import annotations

from katrain.web.session import SessionManager


def _play(session, *coords):
    for c in coords:
        session.katrain("play", coords=c)


def test_history_rows_carry_gtp_coordinates_and_player():
    sm = SessionManager(enable_engine=False)
    session = sm.create_session()
    _play(session, (3, 3), (15, 15), (3, 15))

    history = session.katrain.get_state()["history"]

    # 根节点没有着法 —— 前端的下标口径全靠这一条(第 n 手 = history[n])。
    assert history[0]["move"] is None
    assert history[0]["player"] is None

    assert [(h["player"], h["move"]) for h in history[1:4]] == [
        ("B", "D4"),
        ("W", "Q16"),  # ⚠️ 15 不是 P:GTP 那串**跳过 I**(ABCDEFGHJ…),index 15 = Q
        ("B", "D16"),
    ]


def test_pass_is_the_string_pass_not_none():
    """`None` 已经被根节点占了 —— 虚手再用 `None`,前端就分不出这两件事。"""
    sm = SessionManager(enable_engine=False)
    session = sm.create_session()
    _play(session, (3, 3))
    session.katrain("play", coords=None)  # 虚手

    history = session.katrain.get_state()["history"]
    assert history[2]["move"] == "pass"
    assert history[2]["player"] == "W"


def test_captured_stone_survives_in_history_but_not_in_stones():
    """**这条就是这次改动的全部理由。**

    黑下在 A1 角(0,0),白用 B1 + A2 提掉它。提子之后:
      · `stones` 里 (0,0) **没了**(`_calculate_groups()` 按当前盘面重算);
      · `history` 里那一手**还在** —— 谱记的是「下过什么」,不是「现在盘上有什么」。
    拿 `stones` 拼谱,缺的就是这一手。
    """
    sm = SessionManager(enable_engine=False)
    session = sm.create_session()
    # ⚠️ `Move.gtp()` = 列字母 + (row+1),(0,0) 是 **A1** 不是 A19 —— row 是从下往上数的。
    # B A1 / W B1 / B(别处) / W A2 → 白提掉 A1(角上只有两口气)
    _play(session, (0, 0), (1, 0), (9, 9), (0, 1))

    state = session.katrain.get_state()
    on_board = {tuple(s[1]) for s in state["stones"] if s[1]}
    assert (0, 0) not in on_board, "这一手没被提掉 —— fixture 没造出提子,下面那条就白证了"

    played = [(h["player"], h["move"]) for h in state["history"] if h["move"]]
    assert ("B", "A1") in played, "被提掉的那一手在棋谱里也没了 —— 谱会缺手"
    assert played == [("B", "A1"), ("W", "B1"), ("B", "K10"), ("W", "A2")]
