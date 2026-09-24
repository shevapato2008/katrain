"""Login, logout and identity for the dedicated admin account."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from katrain.web.admin.session import create_session_token, get_current_admin
from katrain.web.core.models_db import AdminAuditLog


router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])
_passwords = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    username: str
    password: str


def _record_auth_event(request: Request, action: str, username: str, success: bool) -> None:
    """Commit an auth audit before confirming login or logout."""
    try:
        with request.app.state.session_factory() as session:
            session.add(
                AdminAuditLog(
                    actor_realm="admin",
                    actor_username=username,
                    action=action,
                    success=success,
                )
            )
            session.commit()
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin audit unavailable"
        ) from error


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    config = request.app.state.admin_config
    password_matches = _passwords.verify(body.password, config.password_hash)
    if body.username != config.username or not password_matches:
        _record_auth_event(request, "login_failed", body.username, False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_session_token(config.username, config.env)
    _record_auth_event(request, "login_success", config.username, True)
    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/me")
async def me(request: Request, admin: dict[str, str] = Depends(get_current_admin)):
    return {"username": admin["username"], "env": request.app.state.admin_config.env}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, admin: dict[str, str] = Depends(get_current_admin)):
    # Sessions are stateless. The frontend removes its Bearer token on logout.
    _record_auth_event(request, "logout", admin["username"], True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
