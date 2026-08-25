from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.models import User, OnlineUser

router = APIRouter()


@router.post("/follow/{username}")
async def follow_user(username: str, request: Request, current_user: User = Depends(get_current_user)) -> Any:
    repo = request.app.state.user_repo
    target_user_dict = repo.get_user_by_username(username)
    if not target_user_dict:
        raise HTTPException(status_code=404, detail="User not found")

    success = repo.follow_user(current_user.id, target_user_dict["id"])
    if not success:
        raise HTTPException(status_code=400, detail="Could not follow user")

    return {"status": "followed"}


@router.delete("/follow/{username}")
async def unfollow_user(username: str, request: Request, current_user: User = Depends(get_current_user)) -> Any:
    repo = request.app.state.user_repo
    target_user_dict = repo.get_user_by_username(username)
    if not target_user_dict:
        raise HTTPException(status_code=404, detail="User not found")

    success = repo.unfollow_user(current_user.id, target_user_dict["id"])
    if not success:
        raise HTTPException(status_code=400, detail="Could not unfollow user")

    return {"status": "unfollowed"}


def _people(rows) -> List[OnlineUser]:
    """一串「人」收窄成 `OnlineUser`。

    ⚠️ 和下面 `/online` 是**同一条理由、同一个修法**:`User` 里带着 `uuid`
    (发给 KataGo 的标识)、`credits`、`is_admin`、`net_wins`,而「关注/粉丝」这两张名单
    一个都不需要(消费方 `galaxy/components/FriendsPanel.tsx` 只用
    id / username / rank / avatar_url)。

    🔴 **2026-08-26:这两条是漏网的。** `/online` 那条 2026-08-25 已经收窄,
    而它上面十一行的这两条**原样留着 `response_model=List[User]`** ——
    同一个文件、同一种泄露、隔着两个函数。
    ⇒ 判据:收窄一个响应模型时,**把同一个文件里回同一种东西的端点一起数一遍**;
    「我改的这一处」和「这一类」不是同一件事。
    """
    return [OnlineUser(**{k: u[k] for k in OnlineUser.model_fields if k in u}) for u in rows]


@router.get("/followers", response_model=List[OnlineUser])
async def get_followers(request: Request, current_user: User = Depends(get_current_user)) -> Any:
    repo = request.app.state.user_repo
    return _people(repo.get_followers(current_user.id))


@router.get("/following", response_model=List[OnlineUser])
async def get_following(request: Request, current_user: User = Depends(get_current_user)) -> Any:
    repo = request.app.state.user_repo
    return _people(repo.get_following(current_user.id))


@router.get("/online", response_model=List[OnlineUser])
async def get_online_users(request: Request, current_user: User = Depends(get_current_user)) -> Any:
    """大厅的「谁在线」。

    ⚠️ 响应模型是 `OnlineUser` **不是 `User`** —— 后者带着 uuid / credits /
    is_admin / net_wins,而这一行一个都不需要。见 `models.OnlineUser` 的说明。
    """
    lobby_manager = request.app.state.lobby_manager
    repo = request.app.state.user_repo
    online_ids = lobby_manager.get_online_user_ids()

    # Fetch user details for these IDs
    all_users = repo.list_users()
    return [OnlineUser(**{k: u[k] for k in OnlineUser.model_fields if k in u}) for u in all_users if u["id"] in online_ids]
