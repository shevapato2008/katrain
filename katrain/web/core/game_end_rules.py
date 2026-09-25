"""终局判定的纯函数 —— 数子门槛怎么随路数缩放、这一局是不是停在「等数子」。

不 import server / session / interface：调用方把 `WebKaTrain` 实例（`session.katrain`）传进来，
这里只读它身上的属性。这样 `get_state`、`/api/move` 的双 pass 钩子和 `/api/count/request`
三处读到的是同一个判定，而不是三份各写各的条件。
"""

#: 盒上模式里「双方各停一手之后该自动数子」的对局类型。升降级双停等待私有云端裁判；
#: 另两种反作弊局（`rated` / `ranked`）保留原行为。
AWAITING_COUNT_GAME_TYPES = frozenset({"free", "pvp_local", "ai_ladder_ranked"})


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
      1. 盒上模式（`suppress_auto_eval`），或云端承载的升降级对局；
      2. 对局类型是自由对弈、本地对局或升降级对弈；
      3. 当前节点和父节点都是 pass；
      4. 当前节点没被认输 / 超时 / 数子写过 `end_state`。

    **不看 `game.manual_score`**：它不是「有人手工定过结果」，而是由 `current_node.score`
    现算的估计（`katrain/core/game.py` 的 `manual_score` 属性）。数子要的正是这份分数
    （`server.py` `_complete_count` 在 score 为 None 时 400），所以分析一回来 manual_score
    就不再为空 —— 把它当条件，数子能成功的那一刻这里恰好翻成假，自动数子会被「已终局」拒掉。
    """
    if not getattr(iface, "suppress_auto_eval", False) and getattr(iface, "game_type", None) != "ai_ladder_ranked":
        return False
    if getattr(iface, "game_type", "free") not in AWAITING_COUNT_GAME_TYPES:
        return False
    game = getattr(iface, "game", None)
    if game is None:
        return False
    node = game.current_node
    parent = getattr(node, "parent", None)
    if parent is None or not getattr(node, "is_pass", False) or not getattr(parent, "is_pass", False):
        return False
    return not node.end_state


def is_time_exhausted(iface) -> bool:
    """轮到的一方钟走完了没有。调用方先 `iface.update_timer()`。

    判据与 `WebKaTrain.update_timer`（`interface.py`）同一套：暂停（不限时）恒 False；
    主时间剩余 ≤ 0；`periods_used` ≥ `max(1, byo_periods)`。`update_timer` 的读秒循环在
    `periods_used` 到 `byo_periods` 时停住，所以 `≥` 与「用尽」等价。
    """
    if getattr(iface, "timer_paused", True):
        return False
    timer = getattr(iface, "active_game_timer", None) or {}
    player = iface.next_player_info.player
    main_left = timer.get("main_time", 0) * 60 - iface.main_time_used_by_player.get(player, 0)
    if main_left > 0:
        return False
    return iface.next_player_info.periods_used >= max(1, timer.get("byo_periods", 5))
