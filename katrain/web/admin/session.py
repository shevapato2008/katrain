"""Eight-hour Bearer sessions signed only by the admin process."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from katrain.web.admin.settings import AdminConfig, check_startup


AUDIENCE = "katrain-admin"
SESSION_TYPE = "admin_session"
SESSION_HOURS = 8


def create_session_token(username: str, env: str, now: datetime | None = None) -> str:
    config = check_startup()
    now = now or datetime.now(timezone.utc)
    claims = {
        "sub": username,
        "type": SESSION_TYPE,
        "aud": AUDIENCE,
        "env": env,
        "exp": now + timedelta(hours=SESSION_HOURS),
    }
    return jwt.encode(claims, config.session_secret, algorithm="HS256")


def username_from_token(token: str, config: AdminConfig) -> str | None:
    try:
        claims = jwt.decode(token, config.session_secret, algorithms=["HS256"], audience=AUDIENCE)
    except JWTError:
        return None
    if (
        claims.get("sub") != config.username
        or claims.get("type") != SESSION_TYPE
        or claims.get("aud") != AUDIENCE
        or claims.get("env") != config.env
    ):
        return None
    expiry = claims.get("exp")
    if isinstance(expiry, bool) or not isinstance(expiry, (int, float)):
        return None
    return config.username


def bearer_token(request: Request) -> str | None:
    scheme, separator, value = request.headers.get("authorization", "").partition(" ")
    token = value.strip()
    return token if separator and scheme.lower() == "bearer" and token else None


async def get_current_admin(request: Request) -> dict[str, str]:
    token = bearer_token(request)
    config: AdminConfig = request.app.state.admin_config
    username = username_from_token(token, config) if token else None
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"realm": "admin", "username": username}
