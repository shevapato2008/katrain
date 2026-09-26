"""Dedicated Bearer-protected local vision lifecycle and paired-frame preview."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
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


def _call(request: Request, operation: str, *args):
    try:
        return getattr(request.app.state.vision_runtime, operation)(*args)
    except VisionError as exc:
        raise HTTPException(exc.status_code, detail=str(exc)) from exc


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
