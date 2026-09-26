"""Dedicated Bearer-protected local vision lifecycle and paired-frame preview."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from katrain.web.admin.session import get_current_admin
from katrain.web.admin.vision_runtime import VisionError

router = APIRouter(dependencies=[Depends(get_current_admin)])


class ConnectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: Annotated[int, Field(strict=True, ge=0, le=8)]
    mode: Literal["stones2", "led4"]


class CalibrateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    empty_confirmed: Annotated[bool, Field(strict=True)] = False


class SgfIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sgf: Annotated[str, Field(strict=True, max_length=2 * 1024 * 1024)]


class CaptureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_id: Annotated[str, Field(strict=True, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
    move_index: Annotated[int, Field(strict=True, ge=-1)]
    operator_confirmed: Annotated[bool, Field(strict=True)] = False
    overwrite_existing: Annotated[bool, Field(strict=True)] = False
    capture_condition: dict = Field(default_factory=dict)


class VerifyGeometryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_id: Annotated[str, Field(strict=True, min_length=1, max_length=128)]
    frame_id: Annotated[str, Field(strict=True, min_length=1, max_length=128)]
    overlay_confirmed: Annotated[bool, Field(strict=True)] = False


class FreezeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    val_fraction: Annotated[float, Field(strict=True, gt=0, lt=1)] = 0.2
    stone_frac: Annotated[float, Field(strict=True, gt=0, le=2)] = 1.05
    led_frac: Annotated[float, Field(strict=True, gt=0, le=2)] = 0.45
    margin_cells: Annotated[float, Field(strict=True, ge=0, le=2)] = 1.0


class SgfOut(BaseModel):
    game_id: str
    sgf_sha256: str
    total_steps: int
    next_step: int | None
    steps: list[dict]
    mode: Literal["stones2", "led4"]


class CaptureOut(BaseModel):
    model_config = ConfigDict(extra="allow")
    frame_id: str
    sha256: str
    captured_at: datetime
    geometry_revision: str
    mode: Literal["stones2", "led4"]
    idempotent: bool


class RuntimeState(BaseModel):
    source: str | None
    updated_at: datetime


class CameraState(RuntimeState):
    state: Literal["unknown", "disconnected", "connecting", "connected", "occupied", "error"]
    device_id: int | None
    error: str | None


class LedState(RuntimeState):
    state: Literal["unknown", "disabled", "disconnected", "connected", "occupied", "error"]
    error: str | None


class GeometryState(RuntimeState):
    state: Literal["required", "ready", "stale"]
    revision: str | None
    confidence: float | None
    error: str | None


class SgfState(RuntimeState):
    state: Literal["none", "loaded"]
    game_id: str | None
    total_steps: int
    next_step: int | None


class DatasetState(RuntimeState):
    state: Literal["none", "draft", "frozen"]
    id: str | None
    count: int


class VisionStatus(BaseModel):
    enabled: bool
    local_only: Literal[True]
    observed_at: datetime
    mode: Literal["stones2", "led4"] | None
    camera: CameraState
    led: LedState
    geometry: GeometryState
    sgf: SgfState
    dataset: DatasetState


class DeviceCandidate(BaseModel):
    device_id: int
    label: str
    probed: Literal[False]


class DevicesOut(BaseModel):
    candidates: list[DeviceCandidate]


class PreviewOut(BaseModel):
    frame_id: str
    captured_at: datetime
    captured_at_source: Literal["runtime_observed_at"]
    camera_seq: int
    camera_monotonic_ts: float
    geometry_revision: str | None
    raw_jpeg_base64: str
    warped_jpeg_base64: str | None
    geometry_overlay_jpeg_base64: str | None


def _call(request: Request, operation: str, *args, **kwargs):
    try:
        return getattr(request.app.state.vision_runtime, operation)(*args, **kwargs)
    except VisionError as exc:
        raise HTTPException(exc.status_code, detail=str(exc), headers={"Cache-Control": "no-store"}) from exc


@router.get("/status", response_model=VisionStatus)
def status(request: Request):
    return _call(request, "status")


@router.get("/devices", response_model=DevicesOut)
def devices(request: Request):
    return _call(request, "devices")


@router.post("/connect", response_model=VisionStatus)
def connect(body: ConnectIn, request: Request):
    return _call(request, "connect", body.device_id, body.mode)


@router.post("/disconnect", response_model=VisionStatus)
def disconnect(request: Request):
    return _call(request, "disconnect")


@router.post("/calibrate", response_model=GeometryState)
def calibrate(body: CalibrateIn, request: Request):
    return _call(request, "calibrate", body.empty_confirmed)


@router.get("/preview", response_model=PreviewOut)
def preview(request: Request):
    return _call(request, "preview")


@router.post("/sgf", response_model=SgfOut)
def import_sgf(body: SgfIn, request: Request):
    return _call(request, "import_sgf", body.sgf)


@router.post("/capture", response_model=CaptureOut)
def capture(body: CaptureIn, request: Request):
    return _call(request, "capture", **body.model_dump())


@router.get("/sessions")
def sessions(request: Request):
    return _call(request, "list_sessions")


@router.get("/sessions/{game_id}")
def session(game_id: str, request: Request):
    return _call(request, "get_session", game_id)


@router.post("/sessions/{game_id}/resume", response_model=VisionStatus)
def resume_session(game_id: str, request: Request):
    return _call(request, "resume_session", game_id)


@router.post("/verify-geometry", response_model=GeometryState)
def verify_geometry(body: VerifyGeometryIn, request: Request):
    return _call(request, "verify_geometry", **body.model_dump())


@router.get("/sessions/{game_id}/frames/{frame_id}/review")
def review_sample(game_id: str, frame_id: str, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return _call(request, "review_sample", game_id, frame_id)


@router.post("/sessions/{game_id}/freeze")
def freeze(body: FreezeIn, game_id: str, request: Request):
    return _call(request, "freeze_dataset", game_id, **body.model_dump())
