"""Frozen cloud API for Xiangqi ranked previews and reservation control."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.core.box_sso import BRIDGE_KEY_HEADER
from katrain.web.core.config import settings
from katrain.web.core.xiangqi_ranked_capabilities import TerminalCapabilityCodec, TerminalCapabilityStore
from katrain.web.core.xiangqi_ranked_repo import XiangqiRankedRepository
from katrain.web.core.xiangqi_ranked_service import RankedServiceError, XiangqiRankedService
from katrain.web.models import User


class RankedAPIRoute(APIRoute):
    """Keep ranked errors top-level without echoing request values or credentials."""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def ranked_handler(request: Request):
            try:
                return await original(request)
            except RequestValidationError as exc:
                fields = sorted(
                    {
                        ".".join(str(part) for part in error["loc"] if part not in {"body", "query", "path"})
                        for error in exc.errors()
                    }
                )
                return JSONResponse(
                    status_code=422,
                    content={"code": "invalid_request", "message": "The ranked request is invalid.", "fields": fields},
                )
            except HTTPException as exc:
                if isinstance(exc.detail, Mapping) and "code" in exc.detail:
                    content = dict(exc.detail)
                else:
                    code = {
                        401: "ranked_login_required",
                        403: "forbidden",
                        404: "not_found",
                    }.get(exc.status_code, "request_failed")
                    content = {"code": code, "message": "The ranked request could not be completed."}
                return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

        return ranked_handler


router = APIRouter(route_class=RankedAPIRoute)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


DeviceId = str
Hash64 = str
GameId = str


class PreviewRequest(StrictModel):
    device_id: DeviceId = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    catalog_version: str = Field(min_length=1, max_length=64)
    supported_contract_versions: list[int] = Field(min_length=1, max_length=32)


class ReservationRequest(StrictModel):
    game_id: GameId = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    device_id: DeviceId = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    expected_profile_version: int = Field(ge=0)
    projection_fingerprint: Hash64 = Field(pattern=r"^[0-9a-f]{64}$")
    scoring_contract_version: int = Field(ge=1)
    catalog_version: str = Field(min_length=1, max_length=64)
    opponent_profile_hash: Hash64 = Field(pattern=r"^[0-9a-f]{64}$")
    time_control: Literal["unlimited", "blitz5", "standard10", "slow20"]


class RotateRequest(StrictModel):
    game_id: GameId = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class EmptyRequest(StrictModel):
    pass


class ForceResignRequest(StrictModel):
    confirm: Literal[True]


class VoidRequest(StrictModel):
    user_uuid: str = Field(min_length=32, max_length=36)
    game_id: GameId = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _service(request: Request) -> XiangqiRankedService:
    service = getattr(request.app.state, "xiangqi_ranked_service", None)
    if service is None and hasattr(request.app.state, "user_repo"):
        session_factory = getattr(request.app.state.user_repo, "session_factory", None)
        if session_factory is not None:
            capabilities = TerminalCapabilityStore(
                session_factory,
                TerminalCapabilityCodec(secret=settings.SECRET_KEY, algorithm=settings.ALGORITHM),
            )
            service = XiangqiRankedService(XiangqiRankedRepository(session_factory), capabilities)
            request.app.state.xiangqi_ranked_service = service
    if service is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "ranked_unavailable", "message": "Xiangqi ranked authority is unavailable."},
        )
    return service


def _call(operation, **kwargs):
    try:
        return operation(**kwargs)
    except RankedServiceError as exc:
        detail = {"code": exc.code, "message": exc.message, **dict(exc.context)}
        raise HTTPException(status_code=exc.status_code, detail=detail) from None


def _terminal_bearer(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_terminal_capability", "message": "Invalid terminal capability."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.removeprefix("Bearer ")
    if not token or " " in token:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_terminal_capability", "message": "Invalid terminal capability."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


@router.post("/previews")
def create_preview(
    request: Request,
    body: PreviewRequest,
    current_user: User = Depends(get_current_user),
):
    return _call(
        _service(request).preview,
        user_uuid=current_user.uuid,
        device_id=body.device_id,
        catalog_version=body.catalog_version,
        supported_contract_versions=body.supported_contract_versions,
    )


@router.post("/reservations", status_code=201)
def create_reservation(
    request: Request,
    body: ReservationRequest,
    current_user: User = Depends(get_current_user),
):
    return _call(_service(request).reserve, user_uuid=current_user.uuid, **body.model_dump())


@router.get("/reservations/current")
def current_reservation(request: Request, current_user: User = Depends(get_current_user)):
    current = _service(request).current(user_uuid=current_user.uuid)
    return current if current is not None else {"code": "current", "reservation": None}


@router.post("/reservations/{reservation_id}/capabilities/rotate")
def rotate_capability(
    reservation_id: str,
    request: Request,
    body: RotateRequest,
    current_user: User = Depends(get_current_user),
):
    return _call(
        _service(request).rotate,
        user_uuid=current_user.uuid,
        reservation_id=reservation_id,
        game_id=body.game_id,
    )


@router.post("/reservations/{reservation_id}/heartbeat")
def heartbeat(
    reservation_id: str,
    request: Request,
    body: EmptyRequest,
    authorization: str | None = Header(default=None),
):
    del body
    return _call(
        _service(request).heartbeat,
        reservation_id=reservation_id,
        terminal_capability=_terminal_bearer(authorization),
    )


@router.post("/reservations/{reservation_id}/force-resign")
def force_resign(
    reservation_id: str,
    request: Request,
    body: ForceResignRequest,
    current_user: User = Depends(get_current_user),
):
    return _call(
        _service(request).force_resign,
        user_uuid=current_user.uuid,
        reservation_id=reservation_id,
        confirm=body.confirm,
    )


@router.post("/reservations/{reservation_id}/void-unmaterialized")
def void_unmaterialized(
    reservation_id: str,
    request: Request,
    body: VoidRequest,
    bridge_key: str | None = Header(default=None, alias=BRIDGE_KEY_HEADER),
):
    client_host = request.client.host if request.client else None
    if not request.app.state.box_sso.authorize_bridge(client_host, bridge_key):
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Forbidden."})
    return _call(
        _service(request).void_unmaterialized,
        user_uuid=body.user_uuid,
        reservation_id=reservation_id,
        game_id=body.game_id,
    )
