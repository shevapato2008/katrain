"""成长屏(围棋 kiosk 屏 22)那几个数的聚合。

**为什么要一个新端点,而不是前端拿列表自己数**:那四格是「近 30 天对局」「升降级胜率」
「累计已解题」「升降级局累计」。前三个里有两个要跨整张表数,而 RK3562 是 2G 内存 ——
为渲染四个数字把整个对局库拉到浏览器里再 filter,和被否掉的「每手轮询 SGF」是同一类错。

**为什么胜率只算升降级局**:`user_games.result` 存的是**哪一方赢**(`"B+R"`),
而这张表**没有任何一列记这个用户坐的是哪一方** —— 拿玩家名去猜(`player_black == username`?)
就是在编。`ai_ladder_game_ledger` 有 `user_color`,它的 `result` 本身就是从这个用户视角写的
win/loss,所以只有升降级局的胜率算得出来。**屏上那一格的标签必须写明这个口径。**

⚠️ **`authority` 这一格不是装饰。** 盒子(board mode)上权威在云端,本机库只是一份缓存;
数出来的数可能**偏小**。「一个数」在屏上天然读作「全部」,所以这里据实交代是哪一种,
由界面去说「本机记录」。**不许悄悄拿本机缓存冒充完整账本** —— 那正是
`repository_dispatcher` 对**列表**做的降级(看得见自己有什么,没问题),
但对**计数**做同样的降级就是撒谎。
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.models import User

router = APIRouter()

#: 屏上那句「近 30 天」。改这个数就要改屏上的标签 —— 所以它是入参,默认写在这里一处。
DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 365


@router.get("/summary")
async def growth_summary(
    request: Request,
    days: int = DEFAULT_WINDOW_DAYS,
    current_user: User = Depends(get_current_user),
):
    if not 1 <= days <= MAX_WINDOW_DAYS:
        raise HTTPException(status_code=422, detail=f"days must be 1..{MAX_WINDOW_DAYS}")

    # 带时区。`created_at` / `settled_at` 都是 `DateTime(timezone=True)`,
    # 而 SQLite 不存时区 —— 单测里那条边界断言只在 PG 上说了算(见测试里的说明)。
    since = datetime.now(timezone.utc) - timedelta(days=days)

    game_repo = getattr(request.app.state, "user_game_repo", None)
    ladder_repo = getattr(request.app.state, "ai_ladder_repo", None)
    if game_repo is None or ladder_repo is None:
        raise HTTPException(status_code=503, detail="growth summary unavailable on this node")

    ladder = ladder_repo.growth_summary(current_user.id, since=since)

    # 盒子上这一份是缓存,权威在云端 ⇒ 数可能偏小。据实交代,界面去说「本机记录」。
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    authority = "local_cache" if dispatcher is not None else "this_node"

    return {
        "window_days": days,
        "games_in_window": game_repo.count_since(current_user.id, since=since),
        "ranked_total": ladder["ranked_total"],
        "ranked_wins_in_window": ladder["ranked_wins_in_window"],
        "ranked_losses_in_window": ladder["ranked_losses_in_window"],
        "by_opponent_rung": ladder["by_opponent_rung"],
        "authority": authority,
    }
