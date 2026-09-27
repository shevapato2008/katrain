"""Box telemetry endpoints: registration (trust on first use) and signed heartbeats.

No user token is involved: a box reports whether or not anyone is logged in on it, and a device's
identity must never be mixed with a person's. See `katrain/web/core/device_telemetry.py`.
"""

import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import delete, func, select

from katrain.web.core import device_telemetry as dt
from katrain.web.core.models_db import BoxDevice

router = APIRouter()
DEVICE_ID = r"^[A-Za-z0-9._-]{1,64}$"


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(pattern=DEVICE_ID)
    key: str = Field(pattern=r"^[0-9a-f]{64}$")
    board: str | None = Field(None, max_length=64)


class Heartbeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    board: str | None = Field(None, max_length=64)
    smartbox_version: str | None = Field(None, max_length=32)
    katrain_build: str | None = Field(None, max_length=64)
    mode: str | None = Field(None, max_length=32)
    uptime_s: int | None = Field(None, ge=0, le=10**9)


def _clock(request: Request) -> float:
    return getattr(request.app.state, "device_clock", time.time)()


def _session(request: Request):
    return request.app.state.session_factory()


@router.post("/register")
def register(body: Registration, request: Request):
    now = datetime.fromtimestamp(_clock(request), timezone.utc)
    with _session(request) as db:
        existing = db.get(BoxDevice, body.device_id)
        if existing is not None:
            if existing.status == "rejected":
                raise HTTPException(status_code=403, detail="device rejected")
            if existing.key != body.key:
                raise HTTPException(status_code=409, detail="device already registered with another key")
            return {"status": existing.status}
        db.execute(
            delete(BoxDevice).where(BoxDevice.status == "pending", BoxDevice.registered_at < now - timedelta(seconds=dt.PENDING_TTL_S))
        )
        pending = db.scalar(select(func.count()).select_from(BoxDevice).where(BoxDevice.status == "pending"))
        if pending >= dt.MAX_PENDING:
            db.commit()
            raise HTTPException(status_code=429, detail="too many pending devices")
        db.add(BoxDevice(device_id=body.device_id, key=body.key, status="pending", registered_at=now, board=body.board))
        db.commit()
    return {"status": "pending"}


@router.post("/heartbeat")
async def heartbeat(
    request: Request,
    x_device_id: str = Header(..., max_length=64),
    x_device_timestamp: str = Header(..., max_length=20),
    x_device_signature: str = Header(..., max_length=128),
):
    raw = await request.body()
    if len(raw) > 4096:
        raise HTTPException(status_code=413, detail="heartbeat too large")
    now = _clock(request)
    try:
        stamp = int(x_device_timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail={"code": "bad_timestamp"})
    if abs(stamp - now) > dt.MAX_SKEW_S:
        raise HTTPException(status_code=401, detail={"code": "clock_skew", "server_time": int(now)})
    with _session(request) as db:
        device = db.get(BoxDevice, x_device_id)
        if device is None or not dt.valid_signature(device.key, x_device_timestamp, raw, x_device_signature):
            raise HTTPException(status_code=401, detail={"code": "unauthorized"})
        if device.status == "rejected":
            raise HTTPException(status_code=403, detail={"code": "rejected"})
        if device.last_ts is not None and stamp <= device.last_ts:
            raise HTTPException(status_code=401, detail={"code": "replay"})
        try:
            body = Heartbeat.model_validate_json(raw or b"{}")
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail="invalid heartbeat fields") from exc
        device.last_ts, device.last_seen = stamp, datetime.fromtimestamp(now, timezone.utc)
        device.last_ip = (request.client.host if request.client else None)
        for field in ("board", "smartbox_version", "katrain_build", "mode", "uptime_s"):
            setattr(device, field, getattr(body, field))
        db.commit()
        return {"status": device.status, "server_time": int(now)}
