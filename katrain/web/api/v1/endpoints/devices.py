"""Box telemetry endpoints: registration (trust on first use) and signed heartbeats.

No user token is involved: a box reports whether or not anyone is logged in on it, and a device's
identity must never be mixed with a person's. See `katrain/web/core/device_telemetry.py`.
"""

import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

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
    ip = dt.client_ip(request)
    with _session(request) as db:
        existing = db.get(BoxDevice, body.device_id)
        if existing is not None:
            return _existing(existing, body.key)
        # A pending registration expires 7 days after the box was last heard from (not after it
        # registered): a box that keeps reporting while nobody approves it is never silently dropped.
        cutoff = now - timedelta(seconds=dt.PENDING_TTL_S)
        db.execute(
            delete(BoxDevice).where(
                BoxDevice.status == "pending",
                or_(BoxDevice.last_seen < cutoff, (BoxDevice.last_seen.is_(None)) & (BoxDevice.registered_at < cutoff)),
            )
        )
        pending = db.scalar(select(func.count()).select_from(BoxDevice).where(BoxDevice.status == "pending"))
        from_ip = db.scalar(select(func.count()).select_from(BoxDevice).where(BoxDevice.status == "pending", BoxDevice.last_ip == ip)) if ip else 0
        if pending >= dt.MAX_PENDING or from_ip >= dt.MAX_PENDING_PER_IP:
            db.commit()
            raise HTTPException(status_code=429, detail="too many pending devices")
        db.add(BoxDevice(device_id=body.device_id, key=body.key, status="pending", registered_at=now, board=body.board, last_ip=ip))
        try:
            db.commit()
        except IntegrityError:  # a concurrent registration of the same id won; answer as for an existing row
            db.rollback()
            return _existing(db.get(BoxDevice, body.device_id), body.key)
    return {"status": "pending"}


def _existing(device: BoxDevice, key: str) -> dict:
    if device.status == "rejected":
        raise HTTPException(status_code=403, detail="device rejected")
    if device.key != key:
        raise HTTPException(status_code=409, detail="device already registered with another key")
    return {"status": device.status}


@router.post("/heartbeat")
async def heartbeat(
    request: Request,
    x_device_id: str = Header(..., max_length=64),
    x_device_timestamp: str = Header(..., max_length=20),
    x_device_signature: str = Header(..., max_length=128),
):
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdigit() or int(declared) > dt.MAX_BODY_BYTES):
        raise HTTPException(status_code=413, detail="heartbeat too large")
    raw = await request.body()
    if len(raw) > dt.MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="heartbeat too large")
    now = _clock(request)
    try:
        stamp = int(x_device_timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail={"code": "bad_timestamp"})
    if abs(stamp - now) > dt.MAX_SKEW_S:
        raise HTTPException(status_code=401, detail={"code": "clock_skew", "server_time": int(now)})
    return await run_in_threadpool(_record, request, x_device_id, stamp, x_device_timestamp, x_device_signature, raw, now)


def _record(request, device_id, stamp, stamp_text, claimed, raw, now) -> dict:
    with _session(request) as db:
        device = db.get(BoxDevice, device_id)
        if device is None or not dt.valid_signature(device.key, stamp_text, raw, claimed):
            raise HTTPException(status_code=401, detail={"code": "unauthorized"})
        if device.status == "rejected":
            raise HTTPException(status_code=403, detail={"code": "rejected"})
        try:
            body = Heartbeat.model_validate_json(raw or b"{}")
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail="invalid heartbeat fields") from exc
        # Conditional on the timestamp so two concurrent copies of one request cannot both pass.
        claimed_slot = db.execute(
            update(BoxDevice)
            .where(BoxDevice.device_id == device_id, or_(BoxDevice.last_ts.is_(None), BoxDevice.last_ts < stamp))
            .values(
                last_ts=stamp, last_seen=datetime.fromtimestamp(now, timezone.utc), last_ip=dt.client_ip(request),
                **{field: getattr(body, field) for field in ("board", "smartbox_version", "katrain_build", "mode", "uptime_s")},
            )
        )
        if claimed_slot.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=401, detail={"code": "replay"})
        db.commit()
        return {"status": device.status, "server_time": int(now)}
