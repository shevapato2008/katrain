"""Legacy admin sessions and dedicated short-lived SmartBox service assertions."""

import math
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from katrain.web.admin.settings import AdminConfig, check_startup


AUDIENCE = "katrain-admin"
SESSION_TYPE = "admin_session"
SESSION_HOURS = 8
SERVICE_ISSUER = "smartbox-admin"
SERVICE_AUDIENCE = "katrain-admin-service"
SERVICE_TYPE = "admin_service"
SERVICE_MAX_LIFETIME_SECONDS = 60
SERVICE_MAX_REQUEST_ID_LENGTH = 128


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
    if config.provider_only:
        return None
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


def username_from_service_assertion(token: str, config: AdminConfig) -> str | None:
    """Verify service identity independently of the player and legacy session keys."""
    if not config.service_secret:
        return None
    try:
        claims = jwt.decode(
            token,
            config.service_secret,
            algorithms=["HS256"],
            audience=SERVICE_AUDIENCE,
            issuer=SERVICE_ISSUER,
            options={"verify_iat": False, "verify_exp": False},
        )
    except (JWTError, ValueError, TypeError, OverflowError):
        return None
    if (
        claims.get("iss") != SERVICE_ISSUER
        or claims.get("aud") != SERVICE_AUDIENCE
        or claims.get("type") != SERVICE_TYPE
        or claims.get("sub") != config.username
        or claims.get("env") != config.env
    ):
        return None
    issued, expiry = claims.get("iat"), claims.get("exp")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or (isinstance(value, float) and not math.isfinite(value))
        for value in (issued, expiry)
    ):
        return None
    now = datetime.now(timezone.utc).timestamp()
    # No skew window: validity is entirely inside the signed, at-most-60-second interval.
    if not issued <= now < expiry <= issued + SERVICE_MAX_LIFETIME_SECONDS:
        return None
    request_id = claims.get("jti")
    if (
        not isinstance(request_id, str)
        or not 0 < len(request_id) <= SERVICE_MAX_REQUEST_ID_LENGTH
        or request_id != request_id.strip()
    ):
        return None
    return config.username


def bearer_token(request: Request) -> str | None:
    scheme, separator, value = request.headers.get("authorization", "").partition(" ")
    token = value.strip()
    return token if separator and scheme.lower() == "bearer" and token else None


async def get_current_admin(request: Request) -> dict[str, str]:
    token = bearer_token(request)
    config: AdminConfig = request.app.state.admin_config
    username = username_from_service_assertion(token, config) or username_from_token(token, config) if token else None
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"realm": "admin", "username": username}
