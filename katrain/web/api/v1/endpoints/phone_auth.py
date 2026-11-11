"""Private mainland-phone authentication, using the cloud as sole account authority."""

from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from katrain.web.api.v1.endpoints.auth import (
    Token,
    _install_board_login,
    _is_admin_username,
    _issue_loopback_sso_cookie,
    get_current_user,
    oauth2_scheme_optional,
)
from katrain.web.core.auth import create_access_token, create_refresh_token
from katrain.web.core.box_sso import is_guest_user, strict_box_sso_enabled
from katrain.web.core.config import settings
from katrain.web.core.phone import normalize_phone
from katrain.web.core.remote_client import CloudIdentityChangedError
from katrain.web.models import User


class PrivatePhoneRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def private_handler(request):
            try:
                response = await handler(request)
            except RequestValidationError as error:
                # Pydantic's default errors include the submitted password/code/
                # phone as `input`. Return only our small public error vocabulary.
                fields = {item["loc"][-1] for item in error.errors()}
                code = (
                    "invalid_phone"
                    if "phone" in fields
                    else "invalid_code" if "code" in fields else "challenge_invalid"
                )
                return JSONResponse(
                    status_code=400, content={"detail": {"code": code}}, headers={"Cache-Control": "no-store"}
                )
            except (ResponseValidationError, SQLAlchemyError):
                # The service transaction has already rolled back. Database
                # errors carry bound phone/code parameters even with echo=False;
                # contain them here without logging or chaining the exception.
                return JSONResponse(
                    status_code=503,
                    content={"detail": {"code": "sms_unavailable"}},
                    headers={"Cache-Control": "no-store"},
                )
            except HTTPException as error:
                error.headers = {**(error.headers or {}), "Cache-Control": "no-store"}
                raise
            response.headers["Cache-Control"] = "no-store"
            return response

        return private_handler


router = APIRouter(route_class=PrivatePhoneRoute)


class PhoneChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str = Field(strict=True, min_length=1, max_length=32)
    purpose: Literal["login", "bind"]
    flow_id: str = Field(strict=True, min_length=22, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class PhoneLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: str = Field(strict=True, min_length=16, max_length=128)
    code: str = Field(strict=True, min_length=6, max_length=6, pattern=r"^[0-9]{6}$")
    flow_id: str = Field(strict=True, min_length=22, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class PhoneBindRequest(PhoneLoginRequest):
    # Missing/empty passwords must reach the service's independently committed
    # reauthentication counter instead of bypassing it in request validation.
    current_password: str | None = Field(default=None, strict=True, max_length=1024)


class PhoneChallengeResponse(BaseModel):
    challenge_id: str
    retry_after: int
    expires_in: int
    delivery: Literal["sent", "unknown"]


class PhoneStatusResponse(BaseModel):
    bound: bool
    masked_phone: str | None = None


def get_phone_otp_service(request: Request):
    from katrain.web.core.phone_otp import PhoneOtpService

    return PhoneOtpService(request.app.state.user_repo.session_factory, settings)


def _raise_service_error(error):
    detail = {"code": error.code}
    if error.retry_after is not None:
        detail["retry_after"] = error.retry_after
    raise HTTPException(status_code=error.status_code, detail=detail) from None


def _raise_remote_error(error):
    if isinstance(error, CloudIdentityChangedError):
        raise HTTPException(status_code=409, detail={"code": "identity_changed"}) from None
    if isinstance(error, httpx.HTTPStatusError):
        allowed = {
            "invalid_phone",
            "invalid_code",
            "challenge_invalid",
            "challenge_expired",
            "challenge_used",
            "authentication_required",
            "bind_reauth_failed",
            "bind_not_allowed",
            "phone_in_use",
            "identity_changed",
            "sms_limited",
            "otp_locked",
            "bind_reauth_locked",
            "sms_unavailable",
            "sms_rejected",
        }
        try:
            detail = error.response.json().get("detail")
            if isinstance(detail, dict) and detail.get("code") in allowed:
                safe_detail = {"code": detail["code"]}
                retry_after = detail.get("retry_after")
                if type(retry_after) is int and 0 <= retry_after <= 86400:
                    safe_detail["retry_after"] = retry_after
                raise HTTPException(status_code=error.response.status_code, detail=safe_detail) from None
        except (ValueError, AttributeError):
            pass
    raise HTTPException(status_code=503, detail={"code": "sms_unavailable"}) from None


async def _phone_user(request: Request, token: str | None = Depends(oauth2_scheme_optional)) -> User:
    try:
        return await get_current_user(request, token)
    except HTTPException:
        raise HTTPException(status_code=401, detail={"code": "authentication_required"}) from None


def _require_bind_actor(user: User) -> None:
    if (
        is_guest_user(user)
        or user.is_admin
        or user.username.strip().lower() == "admin"
        or _is_admin_username(user.username)
    ):
        raise HTTPException(status_code=403, detail={"code": "bind_not_allowed"})


@router.post("/challenges", response_model=PhoneChallengeResponse)
async def phone_challenge(
    request: Request, body: PhoneChallengeRequest, token: str | None = Depends(oauth2_scheme_optional)
):
    from katrain.web.core.phone_otp import PhoneOtpError

    actor = None
    try:
        normalize_phone(body.phone)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "invalid_phone"}) from None
    if body.purpose == "bind":
        actor = await _phone_user(request, token)
        _require_bind_actor(actor)
    elif strict_box_sso_enabled():
        raise HTTPException(status_code=403, detail={"code": "bind_not_allowed"})
    remote = getattr(request.app.state, "remote_client", None)
    if remote is not None:
        try:
            return await remote.phone_challenge(body.model_dump(), expected_user_id=actor.id if actor else None)
        except (httpx.HTTPError, ValueError) as error:
            _raise_remote_error(error)
    try:
        # Both deployed sites currently have an empty proxy trust list. Do not
        # consume attacker-controlled forwarded headers, even their first value.
        return await get_phone_otp_service(request).request_challenge(
            phone=body.phone,
            purpose=body.purpose,
            flow_id=body.flow_id,
            client_ip=request.client.host if request.client else "unknown",
            actor_id=actor.id if actor else None,
        )
    except PhoneOtpError as error:
        _raise_service_error(error)


@router.post("/login", response_model=Token)
async def phone_login(request: Request, response: Response, body: PhoneLoginRequest):
    from katrain.web.core.phone_otp import PhoneOtpError

    if strict_box_sso_enabled():
        raise HTTPException(status_code=403, detail={"code": "bind_not_allowed"})
    remote = getattr(request.app.state, "remote_client", None)
    if remote is not None:
        try:
            candidate = await remote.phone_login(body.model_dump())
        except (httpx.HTTPError, ValueError) as error:
            _raise_remote_error(error)
        return _install_board_login(request, response, candidate)
    try:
        user = get_phone_otp_service(request).login(**body.model_dump())
    except PhoneOtpError as error:
        _raise_service_error(error)
    access = create_access_token(data={"sub": user["username"]})
    refresh = create_refresh_token(data={"sub": user["username"]})
    _issue_loopback_sso_cookie(request, response, access)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


@router.get("/status", response_model=PhoneStatusResponse, response_model_exclude_none=True)
async def phone_status(request: Request, user: User = Depends(_phone_user)):
    from katrain.web.core.phone_otp import PhoneOtpError

    remote = getattr(request.app.state, "remote_client", None)
    if remote is not None:
        try:
            return await remote.phone_status(expected_user_id=user.id)
        except (httpx.HTTPError, ValueError) as error:
            _raise_remote_error(error)
    try:
        return get_phone_otp_service(request).status(user_id=user.id)
    except PhoneOtpError as error:
        _raise_service_error(error)


@router.post("/bind", response_model=PhoneStatusResponse, response_model_exclude_none=True)
async def phone_bind(request: Request, body: PhoneBindRequest, user: User = Depends(_phone_user)):
    from katrain.web.core.phone_otp import PhoneOtpError

    _require_bind_actor(user)
    remote = getattr(request.app.state, "remote_client", None)
    if remote is not None:
        try:
            return await remote.phone_bind(body.model_dump(), expected_user_id=user.id)
        except (httpx.HTTPError, ValueError) as error:
            _raise_remote_error(error)
    try:
        return get_phone_otp_service(request).bind(user_id=user.id, **body.model_dump())
    except PhoneOtpError as error:
        _raise_service_error(error)
