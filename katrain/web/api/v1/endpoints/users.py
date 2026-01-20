from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.models import User

router = APIRouter()

@router.post("/follow/{username}")
async def follow_user(
    username: str, 
    request: Request, 
    current_user: User = Depends(get_current_user)
) -> Any:
    repo = request.app.state.user_repo
    target_user_dict = repo.get_user_by_username(username)
    if not target_user_dict:
        raise HTTPException(status_code=404, detail="User not found")
    
    success = repo.follow_user(current_user.id, target_user_dict["id"])
    if not success:
        raise HTTPException(status_code=400, detail="Could not follow user")
    
    return {"status": "followed"}

@router.delete("/follow/{username}")
async def unfollow_user(
    username: str, 
    request: Request, 
    current_user: User = Depends(get_current_user)
) -> Any:
    repo = request.app.state.user_repo
    target_user_dict = repo.get_user_by_username(username)
    if not target_user_dict:
        raise HTTPException(status_code=404, detail="User not found")
    
    success = repo.unfollow_user(current_user.id, target_user_dict["id"])
    if not success:
        raise HTTPException(status_code=400, detail="Could not unfollow user")
    
    return {"status": "unfollowed"}

@router.get("/followers", response_model=List[User])
async def get_followers(
    request: Request, 
    current_user: User = Depends(get_current_user)
) -> Any:
    repo = request.app.state.user_repo
    followers = repo.get_followers(current_user.id)
    return [User(**u) for u in followers]

@router.get("/following", response_model=List[User])
async def get_following(
    request: Request, 
    current_user: User = Depends(get_current_user)
) -> Any:
    repo = request.app.state.user_repo
    following = repo.get_following(current_user.id)
    return [User(**u) for u in following]
