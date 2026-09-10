import logging
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from katrain.web.core.auth import verify_password, create_access_token, create_refresh_token
from katrain.web.core.box_sso import (
    BRIDGE_KEY_HEADER,
    resolve_http_token,
    strict_box_sso_enabled,
)
from katrain.web.core import models_db, sms, sms_challenge
from katrain.web.core.client_ip import client_ip_for_ratelimit
from katrain.web.core.config import settings
from katrain.web.core.db import get_db
from katrain.web.core.phone import normalize_e164, mask_e164
from katrain.web.models import PhoneLoginRequest, SendCodeRequest, User, UserInDB
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger("katrain_web")

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")
# Optional variant (no auto 401) so we can fall back to the shared SSO cookie.
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

# Box-level SSO (see superpowers/tracks/box-sso-2026-07-13): the launcher (:8080)
# sets this 127.0.0.1-scoped cookie after a successful katrain login, so every app
# on the box shares one identity. The cookie is authoritative for ordinary user
# authentication.
SSO_COOKIE_NAME = "sb_token"
SSO_LOOPBACK_HOST = "127.0.0.1"


VALID_PURPOSES = {"login", "bind", "set_password"}


def _guard_phone_endpoint(request: Request) -> None:
    """四个手机端点共用的盒子闸（spec §2.6）。

    strict 盒子：云端账号体系的事，盒子上没有入口 ⇒ 403，与 /login /register 同形。
    board 非 strict：**不转发**。remote_client 是逐方法手写的，加转发方法等于给盒子
    多开几个故障面；而盒子是共用触摸设备，在上面输手机号收码是最差的绑定场景。
    """
    if strict_box_sso_enabled():
        raise HTTPException(status_code=403, detail={"code": "phone_disabled_on_device",
                                       "message": "请在 modelstella.com 上完成手机号相关操作"})
    if getattr(request.app.state, "remote_client", None) is not None:
        raise HTTPException(
            status_code=503,
            detail={"code": "need_online_phone",
                    "message": "请在 modelstella.com 登录后绑定手机号"},
        )


@router.post("/phone/send-code")
async def send_phone_code(request: Request, body: SendCodeRequest, db: Session = Depends(get_db)):
    _guard_phone_endpoint(request)
    if body.purpose not in VALID_PURPOSES:
        raise HTTPException(status_code=400, detail={"code": "bad_purpose"})
    try:
        phone = normalize_e164(body.phone)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_phone"})

    # **不要用 request.client.host**（F10：生产上它对所有用户恒为 172.20.0.1）。
    ip = client_ip_for_ratelimit(request)
    try:
        cid = await sms_challenge.issue(db, phone, body.purpose, ip)
    except sms_challenge.RateLimited as e:
        # 字段恒在（没有理由时为 None），不要"有理由才有字段" ——
        # 后者逼前端写 `'retry_after_sec' in x` 而不是 `x.retry_after_sec`。
        detail = {"code": e.code, "retry_after_sec": e.retry_after_sec}
        headers = {}
        if e.retry_after_sec is not None:
            headers["Retry-After"] = str(e.retry_after_sec)
        # **日总量打满是 503 不是 429**：那是服务端自己容量到顶，跟这个用户快不快无关。
        raise HTTPException(
            status_code=503 if e.code == "sms_capacity" else 429,
            detail=detail, headers=headers or None,
        )
    except sms.SmsProviderError:
        # **502 而不是 503，是刻意与上面那条区分开的。** 日额度打满要等到明天（我们自己的闸），
        # 供应商抖动几秒后就该重试。合成一个码，前端只能给一句含糊的"稍后再试"。
        raise HTTPException(status_code=502, detail={"code": "sms_provider_failed"})

    # **响应对"这个号有没有账号"必须一模一样** —— 多一个字段这里就是账号枚举器。
    return {"challenge_id": cid, "cooldown_sec": settings.SMS_COOLDOWN_SEC}


@router.post("/phone/login")
async def phone_login(request: Request, body: PhoneLoginRequest, db: Session = Depends(get_db)):
    _guard_phone_endpoint(request)
    try:
        # purpose 写死 "login"：绑定用的码不能拿来登录。
        phone = sms_challenge.verify_and_consume(db, body.challenge_id, body.code, "login")
    except sms_challenge.ChallengeInvalid as e:
        raise HTTPException(status_code=400, detail={"code": e.code})

    user = request.app.state.user_repo.get_by_phone(phone)
    if user is None:
        # 本轮不做手机注册（见 plan 开头的收窄说明）。给一条能走的路，不静默建号。
        raise HTTPException(
            status_code=404,
            detail={"code": "phone_not_bound",
                    "message": "这个手机号还没有绑定账号。请先用用户名密码登录，再到设置里绑定。"},
        )
    return {
        "access_token": create_access_token(data={"sub": user["username"]}),
        "token_type": "bearer",
    }


def _resolve_token(request: Request, header_token: Optional[str]) -> Optional[str]:
    """Select the credential allowed by the active server/strict-box mode."""
    return resolve_http_token(request, header_token)


def _issue_loopback_sso_cookie(request: Request, response: Response, access_token: str) -> None:
    """Persist a direct kiosk login only on the known loopback host.

    The explicit host gate preserves the Galaxy JSON-token flow and avoids
    emitting an invalid `Domain=127.0.0.1` cookie for other hosts.
    """
    if strict_box_sso_enabled() or request.url.hostname != SSO_LOOPBACK_HOST:
        return

    response.set_cookie(
        key=SSO_COOKIE_NAME,
        value=access_token,
        domain=SSO_LOOPBACK_HOST,
        path="/",
        httponly=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def _clear_loopback_sso_cookie(request: Request, response: Response) -> None:
    """Expire the shared SSO cookie only for a direct loopback logout."""
    if request.url.hostname != SSO_LOOPBACK_HOST:
        return

    response.delete_cookie(
        key=SSO_COOKIE_NAME,
        domain=SSO_LOOPBACK_HOST,
        path="/",
        httponly=True,
        samesite="lax",
    )


# Shadow user: placeholder hash that cannot pass verify_password (design 5.3)
SHADOW_USER_NO_LOCAL_AUTH = "SHADOW_USER_NO_LOCAL_AUTH"


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class BoxBootstrapRequest(BaseModel):
    username: str
    generation: int
    remote_access_token: str
    remote_refresh_token: str


class BoxClearRequest(BaseModel):
    generation: int


async def get_user_from_token(token: str, repo: Any, box_sso: Any = None) -> User:
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
        if strict_box_sso_enabled() and (box_sso is None or not box_sso.validates(payload.get("box_generation"))):
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user_dict = repo.get_user_by_username(username)
    if user_dict is None:
        raise credentials_exception
    return User(**user_dict)


async def get_current_user(request: Request, token: Optional[str] = Depends(oauth2_scheme_optional)) -> User:
    resolved = _resolve_token(request, token)
    if not resolved:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await get_user_from_token(
        resolved,
        request.app.state.user_repo,
        getattr(request.app.state, "box_sso", None),
    )


async def get_current_admin_user(request: Request, token: Optional[str] = Depends(oauth2_scheme_optional)) -> User:
    """Require an authenticated user with the is_admin flag. Shadow users never qualify."""
    # Preserve the public/server contract: admin endpoints require an explicit
    # Bearer token there. Strict Box mode has no browser Bearer path, so its
    # generation-bound Go cookie is the only permitted credential.
    resolved = _resolve_token(request, token) if strict_box_sso_enabled() else token
    if not resolved:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    current_user = await get_user_from_token(
        resolved,
        request.app.state.user_repo,
        getattr(request.app.state, "box_sso", None),
    )
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user


# Optional auth - returns None if not authenticated (header or shared SSO cookie).
async def get_current_user_optional(
    request: Request, token: Optional[str] = Depends(oauth2_scheme_optional)
) -> User | None:
    resolved = _resolve_token(request, token)
    if not resolved:
        return None
    try:
        return await get_user_from_token(
            resolved,
            request.app.state.user_repo,
            getattr(request.app.state, "box_sso", None),
        )
    except HTTPException:
        return None


def _get_or_create_shadow_user(repo: Any, username: str) -> dict:
    """Get existing local user or create a shadow user for board-mode auth (design 5.3)."""
    user_dict = repo.get_user_by_username(username)
    if user_dict:
        return user_dict
    return repo.create_user(username=username, hashed_password=SHADOW_USER_NO_LOCAL_AUTH)


def _require_bridge(request: Request) -> Any:
    if not strict_box_sso_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    state = request.app.state.box_sso
    client_host = request.client.host if request.client else None
    if not state.authorize_bridge(client_host, request.headers.get(BRIDGE_KEY_HEADER)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return state


@router.post("/box-sso/bootstrap")
async def box_sso_bootstrap(request: Request, body: BoxBootstrapRequest) -> Any:
    state = _require_bridge(request)
    if isinstance(body.generation, bool) or body.generation <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid generation")
    if not body.username.strip() or not body.remote_access_token or not body.remote_refresh_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid bootstrap payload")
    remote_client = getattr(request.app.state, "remote_client", None)
    if remote_client is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Board client unavailable")
    remote_client.set_tokens(body.remote_access_token, body.remote_refresh_token)
    shadow_user = _get_or_create_shadow_user(request.app.state.user_repo, body.username)
    # Tie the cloud session to this local user so per-user queued work (rank events)
    # can tell whose session is currently up on a shared board.
    remote_client.bind_user(shadow_user["id"])
    await state.activate(body.generation)
    local_access = create_access_token(data={"sub": shadow_user["username"]}, box_generation=body.generation)
    return {"access_token": local_access, "token_type": "bearer"}


@router.post("/box-sso/clear")
async def box_sso_clear(request: Request, body: BoxClearRequest) -> Any:
    state = _require_bridge(request)
    if not await state.clear(body.generation):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stale generation")
    remote_client = getattr(request.app.state, "remote_client", None)
    if remote_client is not None:
        remote_client.clear_tokens()
    return {"ok": True}


@router.post("/login", response_model=Token)
async def login(request: Request, login_data: LoginRequest, response: Response) -> Any:
    if strict_box_sso_enabled():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Direct login disabled")
    remote_client = getattr(request.app.state, "remote_client", None)

    if remote_client is not None:
        # Board mode: forward to remote server (design 5.1)
        try:
            remote_data = await remote_client.login(login_data.username, login_data.password)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except (httpx.ConnectError, httpx.TimeoutException):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cannot connect to remote server",
            )

        # Persist remote refresh_token to encrypted file
        if remote_data.get("refresh_token"):
            from katrain.web.core.credentials import save_refresh_token

            save_refresh_token(settings.DEVICE_ID, remote_data["refresh_token"])

        # Get or create local shadow user (design 5.3)
        repo = request.app.state.user_repo
        shadow_user = _get_or_create_shadow_user(repo, login_data.username)
        remote_client.bind_user(shadow_user["id"])

        # Issue local tokens (design 5.2)
        local_access = create_access_token(data={"sub": shadow_user["username"]})
        local_refresh = create_refresh_token(data={"sub": shadow_user["username"]})
        _issue_loopback_sso_cookie(request, response, local_access)
        return {"access_token": local_access, "token_type": "bearer", "refresh_token": local_refresh}

    # Server mode: local authentication
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
    _issue_loopback_sso_cookie(request, response, access_token)
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}


@router.post("/refresh", response_model=Token)
async def refresh(request: Request, body: RefreshRequest) -> Any:
    """Exchange a valid refresh token for a new access token."""
    if strict_box_sso_enabled():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Direct refresh disabled")
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

    # Board mode: also refresh remote tokens (best-effort, design 5.1)
    remote_client = getattr(request.app.state, "remote_client", None)
    if remote_client is not None:
        try:
            await remote_client._refresh_access_token()
        except Exception:
            logger.debug("Remote token refresh failed (best-effort), local refresh continues")

    new_access_token = create_access_token(data={"sub": username})
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/register", response_model=User)
async def register(request: Request, register_data: LoginRequest, db: Session = Depends(get_db)) -> Any:
    if strict_box_sso_enabled():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Direct registration disabled")
    remote_client = getattr(request.app.state, "remote_client", None)

    if remote_client is not None:
        # Board mode: forward to remote server (design 5.1)
        try:
            remote_user = await remote_client.register(register_data.username, register_data.password)
            return User(**remote_user)
        except httpx.HTTPStatusError as e:
            detail = str(e)
            try:
                detail = e.response.json().get("detail", detail)
            except Exception:
                pass
            raise HTTPException(status_code=e.response.status_code, detail=detail)
        except (httpx.ConnectError, httpx.TimeoutException):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cannot connect to remote server",
            )

    # Server mode: local registration
    from katrain.web.core.auth import get_password_hash

    # /auth/register 至今零限流。P3 建了 per-IP 限流器就给它用上。
    # **位置在 remote_client 转发分支之后**：盒子上的注册原样转发给云端，
    # 不许先在本地库上数一遍 —— 那是给盒子凭空多开一个故障面（D-U3）。
    # 日界与短信额度共用 sms_challenge.today_start()（东八区零点换算成 UTC）；
    # SQLite 的 CURRENT_TIMESTAMP 与 PG 的 now() 存的都是 UTC，两边比的都是 UTC。
    ip = client_ip_for_ratelimit(request)
    signups_today = (
        db.query(func.count(models_db.User.id))
        .filter(
            models_db.User.signup_ip == ip,
            models_db.User.created_at >= sms_challenge.today_start(),
        )
        .scalar()
    )
    if signups_today >= settings.REGISTER_IP_DAILY:
        raise HTTPException(status_code=429, detail={"code": "register_ip_daily"})

    repo = request.app.state.user_repo
    try:
        user_dict = repo.create_user(
            username=register_data.username,
            hashed_password=get_password_hash(register_data.password),
            signup_ip=ip,
        )
        # New accounts start at 0 credits (models_db.User.credits default). Any signup
        # grant is opt-in via settings.BILLING_SIGNUP_GRANT and goes through billing.grant
        # so it lands as a real, auditable ledger row instead of a silent column default.
        if settings.BILLING_SIGNUP_GRANT > 0:
            from katrain.web.core import billing

            user_dict["credits"] = billing.grant(
                db,
                user_dict["id"],
                settings.BILLING_SIGNUP_GRANT,
                "signup",
                f"signup:{user_dict['id']}",
            )
        return User(**user_dict)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)) -> Any:
    return current_user


@router.post("/phone/bind")
async def bind_phone(
    request: Request,
    body: PhoneLoginRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """把手机号绑到当前账号上。**先核销验证码，再查号码归属。**

    反过来这个端点就是号码枚举器 —— 任何登录用户可逐个探测「这个号有没有账号」。
    核销在前意味着你必须先控制这个号，才配知道它被占了。

    （位置：它不能跟 send-code / phone-login 放在一起 —— 那两个在模块前半段，
    而 `get_current_user` 定义在本文件中段，`Depends(get_current_user)` 在函数定义时
    就要解析这个名字。）
    """
    _guard_phone_endpoint(request)
    try:
        phone = sms_challenge.verify_and_consume(db, body.challenge_id, body.code, "bind")
    except sms_challenge.ChallengeInvalid as e:
        raise HTTPException(status_code=400, detail={"code": e.code})

    outcome = request.app.state.user_repo.bind_phone(current_user.id, phone)
    if outcome == "phone_taken":
        raise HTTPException(
            status_code=409,
            detail={"code": "phone_taken",
                    "message": "这个手机号已经有账号了。可以直接用验证码登录那个账号。"},
        )
    if outcome == "already_bound":
        # **不做自助换绑。** 换绑就是旧号的解绑，而「一号一账号」的经济论证与
        # Task 11 那条「未绑号不建桶」的短路都以「不存在解绑路径」为前提。
        raise HTTPException(
            status_code=409,
            detail={"code": "already_bound",
                    "message": "这个账号已经绑定了手机号。换绑请联系客服。"},
        )
    return {"phone_masked": mask_e164(phone)}


@router.post("/logout")
async def logout(request: Request, response: Response, current_user: User = Depends(get_current_user)) -> Any:
    """Logout and cleanup user's active sessions"""
    if strict_box_sso_enabled():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Use Box SSO bridge clear")
    from katrain.web.session import SessionManager, LobbyManager

    _clear_loopback_sso_cookie(request, response)

    # Board mode: clear remote tokens + delete credential file (design 5.4)
    remote_client = getattr(request.app.state, "remote_client", None)
    if remote_client is not None:
        remote_client.clear_tokens()
        from katrain.web.core.credentials import delete_credentials

        delete_credentials(settings.DEVICE_ID)

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
            session_manager.broadcast_to_session(
                session_id,
                {
                    "type": "game_end",
                    "data": {
                        "reason": "forfeit",
                        "winner_id": winner_id,
                        "leaver_id": current_user.id,
                        "result": f"{'W' if session.player_b_id == current_user.id else 'B'}+Forfeit",
                    },
                },
            )

            # Record game result (best-effort — must not block session cleanup).
            # Route through record_multiplayer_game (the single guarded recording
            # path); it skips synthetic opponent ids (<=0), so engine games record
            # only the human. NOTE: GameRepository has no `record_game` method --
            # the previous call here always raised AttributeError and recorded nothing.
            game_repo = request.app.state.game_repo
            if game_repo:
                try:
                    game_repo.record_multiplayer_game(
                        sgf_content=session.katrain.get_sgf(),
                        result=f"{'W' if session.player_b_id == current_user.id else 'B'}+Forfeit",
                        game_type=getattr(session, "game_type", "free"),
                        black_id=session.player_b_id,
                        white_id=session.player_w_id,
                    )
                except Exception as rec_err:
                    import logging

                    logging.getLogger("katrain_web").error(f"Failed to record forfeit on logout: {rec_err}")

            # Remove session
            session_manager.remove_session(session_id)
        except Exception as e:
            import logging

            logging.getLogger("katrain_web").error(f"Error cleaning up session {session_id}: {e}")

    return {"status": "ok", "message": "Logged out successfully"}
