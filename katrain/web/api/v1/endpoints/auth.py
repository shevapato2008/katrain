from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from katrain.web.core.auth import verify_password, create_access_token, create_refresh_token
from katrain.web.core.config import settings
from katrain.web.models import User, UserInDB

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str

async def get_user_from_token(token: str, repo: Any) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user_dict = repo.get_user_by_username(username)
    if user_dict is None:
        raise credentials_exception
    return User(**user_dict)

async def get_current_user(request: Request, token: str = Depends(oauth2_scheme)) -> User:
    return await get_user_from_token(token, request.app.state.user_repo)

# Optional auth - returns None if not authenticated, doesn't require token
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

async def get_current_user_optional(request: Request, token: str = Depends(oauth2_scheme_optional)) -> User | None:
    if not token:
        return None
    try:
        return await get_user_from_token(token, request.app.state.user_repo)
    except HTTPException:
        return None

@router.post("/login", response_model=Token)
async def login(request: Request, login_data: LoginRequest) -> Any:
    repo = request.app.state.user_repo
    user_dict = repo.get_user_by_username(login_data.username)
    if not user_dict or not verify_password(login_data.password, user_dict["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user_dict["username"]})
    refresh_token = create_refresh_token(data={"sub": user_dict["username"]})
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

@router.post("/refresh", response_model=Token)
async def refresh(request: Request, body: RefreshRequest) -> Any:
    """Exchange a valid refresh token for a new access token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(body.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_type: str = payload.get("type")
        username: str = payload.get("sub")
        if token_type != "refresh" or username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    repo = request.app.state.user_repo
    user_dict = repo.get_user_by_username(username)
    if user_dict is None:
        raise credentials_exception

    new_access_token = create_access_token(data={"sub": username})
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/register", response_model=User)
async def register(request: Request, register_data: LoginRequest) -> Any:
    from katrain.web.core.auth import get_password_hash
    repo = request.app.state.user_repo
    try:
        user_dict = repo.create_user(
            username=register_data.username, 
            hashed_password=get_password_hash(register_data.password)
        )
        return User(**user_dict)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)) -> Any:
    return current_user

@router.post("/logout")
async def logout(request: Request, current_user: User = Depends(get_current_user)) -> Any:
    """Logout and cleanup user's active sessions"""
    from katrain.web.session import SessionManager, LobbyManager

    # Clean up from lobby if present
    lobby_manager: LobbyManager = request.app.state.lobby_manager
    with lobby_manager._lock:
        if current_user.id in lobby_manager._online_users:
            # Close all lobby websockets for this user
            sockets = list(lobby_manager._online_users.pop(current_user.id, []))
            for ws in sockets:
                try:
                    # Send a logout notification before closing
                    import asyncio
                    asyncio.create_task(ws.close(code=1000, reason="User logged out"))
                except:
                    pass

    # Clean up from matchmaker queue if present
    matchmaker = request.app.state.matchmaker
    matchmaker.remove_from_queue(current_user.id)

    # Find and cleanup any multiplayer sessions where user is a player
    session_manager: SessionManager = request.app.state.session_manager
    sessions_to_cleanup = []
    with session_manager._lock:
        for session_id, session in session_manager._sessions.items():
            if session.player_b_id == current_user.id or session.player_w_id == current_user.id:
                sessions_to_cleanup.append(session_id)

    # Handle forfeit for each active game
    for session_id in sessions_to_cleanup:
        try:
            session = session_manager.get_session(session_id)
            # Determine winner (the other player)
            winner_id = session.player_w_id if session.player_b_id == current_user.id else session.player_b_id

            # Broadcast game end
            session_manager.broadcast_to_session(session_id, {
                "type": "game_end",
                "data": {
                    "reason": "forfeit",
                    "winner_id": winner_id,
                    "leaver_id": current_user.id,
                    "result": f"{'W' if session.player_b_id == current_user.id else 'B'}+Forfeit"
                }
            })

            # Record game result
            game_repo = request.app.state.game_repo
            if game_repo and winner_id:
                game_repo.record_game(
                    black_id=session.player_b_id,
                    white_id=session.player_w_id,
                    result=f"{'W' if session.player_b_id == current_user.id else 'B'}+Forfeit",
                    winner_id=winner_id
                )

            # Remove session
            session_manager.remove_session(session_id)
        except Exception as e:
            import logging
            logging.getLogger("katrain_web").error(f"Error cleaning up session {session_id}: {e}")

    return {"status": "ok", "message": "Logged out successfully"}
