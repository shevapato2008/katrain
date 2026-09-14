"""终局判定的纯函数 —— 数子门槛怎么随路数缩放、这一局是不是停在「等数子」。

不 import server / session / interface：调用方把 `WebKaTrain` 实例（`session.katrain`）传进来，
这里只读它身上的属性。这样 `get_state`、`/api/move` 的双 pass 钩子和 `/api/count/request`
三处读到的是同一个判定，而不是三份各写各的条件。
"""

#: 盒上模式里「双方各停一手之后该自动数子」的对局类型。升降级（`ai_ladder_ranked`）与
#: 两种反作弊局（`rated` / `ranked`）不在里面：它们的终局今天怎么落账，本轮不动。
AWAITING_COUNT_GAME_TYPES = frozenset({"free", "pvp_local"})


def scaled_count_min_moves(base: int, board_size: int) -> int:
    """手动数子的最少手数，按棋盘面积从 19 路的 `base` 缩放。

    base=100 时 19 路 100、13 路 47、9 路 22。`max(1, …)` 让配置成 0 的「不设门槛」
    仍然成立：比较对象 `len(state["history"])` 含根节点，恒 ≥ 1。
    n < 19 时 base·n²/361 不可能恰好落在 .5 上（361 = 19²，与 n² 互素），
    所以 Python 的银行家舍入与前端 Math.round 不会分叉。
    """
    return max(1, round(int(base) * board_size * board_size / 361))


def is_awaiting_count(iface) -> bool:
    """这一局是不是停在「双方各停一手、还没数子」。

    四条同时成立才为真：
      1. 盒上模式（`suppress_auto_eval`）—— galaxy 走不到；
      2. 对局类型是自由对弈或本地对局；
      3. 当前节点和父节点都是 pass；
      4. 当前节点没被认输 / 超时 / 数子写过 `end_state`。

    **不看 `game.manual_score`**：它不是「有人手工定过结果」，而是由 `current_node.score`
    现算的估计（`katrain/core/game.py` 的 `manual_score` 属性）。数子要的正是这份分数
    （`server.py` `_complete_count` 在 score 为 None 时 400），所以分析一回来 manual_score
    就不再为空 —— 把它当条件，数子能成功的那一刻这里恰好翻成假，自动数子会被「已终局」拒掉。
    """
    if not getattr(iface, "suppress_auto_eval", False):
        return False
    if getattr(iface, "game_type", "free") not in AWAITING_COUNT_GAME_TYPES:
        return False
    game = getattr(iface, "game", None)
    if game is None:
        return False
    node = game.current_node
    parent = node.parent
    if parent is None or not node.is_pass or not parent.is_pass:
        return False
    return not node.end_state
