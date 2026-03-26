"""Board device management endpoints.

Server-side: heartbeat, device listing (design.md Section 4.15).
Board-side: live match proxy to remote server (when KATRAIN_MODE=board).
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.core.db import get_db
from katrain.web.core.models_db import DeviceHeartbeatDB
from katrain.web.models import User

logger = logging.getLogger("katrain_web")

router = APIRouter()


class HeartbeatRequest(BaseModel):
    device_id: str
    queue_depth: int = 0
    failed_count: int = 0
    oldest_unsynced_age_sec: int = 0
    app_version: Optional[str] = None


class HeartbeatResponse(BaseModel):
    status: str  # "ok" or "upgrade_available"
    server_time: str
    upgrade_url: Optional[str] = None


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def device_heartbeat(
    request: Request,
    body: HeartbeatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Receive heartbeat from an RK3588 board device.

    Updates last_seen timestamp and sync queue stats for monitoring.
    """
    now = datetime.utcnow()

    # Upsert device heartbeat record
    record = db.query(DeviceHeartbeatDB).filter(
        DeviceHeartbeatDB.device_id == body.device_id
    ).first()

    if record:
        record.last_seen = now
        record.queue_depth = body.queue_depth
        record.failed_count = body.failed_count
        record.oldest_unsynced_age_sec = body.oldest_unsynced_age_sec
        record.app_version = body.app_version
        record.ip_address = request.client.host if request.client else None
    else:
        record = DeviceHeartbeatDB(
            device_id=body.device_id,
            last_seen=now,
            queue_depth=body.queue_depth,
            failed_count=body.failed_count,
            oldest_unsynced_age_sec=body.oldest_unsynced_age_sec,
            app_version=body.app_version,
            ip_address=request.client.host if request.client else None,
        )
        db.add(record)

    db.commit()

    return HeartbeatResponse(
        status="ok",
        server_time=now.isoformat(),
    )


@router.get("/devices")
async def list_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all registered board devices (admin monitoring)."""
    devices = db.query(DeviceHeartbeatDB).order_by(
        DeviceHeartbeatDB.last_seen.desc()
    ).all()

    return [
        {
            "device_id": d.device_id,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            "queue_depth": d.queue_depth,
            "failed_count": d.failed_count,
            "oldest_unsynced_age_sec": d.oldest_unsynced_age_sec,
            "app_version": d.app_version,
            "ip_address": d.ip_address,
        }
        for d in devices
    ]


# ── Live Match Proxy (board mode only) ──
# When KATRAIN_MODE=board, live_service is not started.
# These endpoints proxy live match requests to the remote server.


def _get_remote_client(request: Request):
    """Get RemoteAPIClient from app state (board mode only)."""
    client = getattr(request.app.state, "remote_client", None)
    if not client:
        raise HTTPException(status_code=503, detail="Not in board mode")
    return client


@router.get("/live/matches")
async def proxy_live_matches(
    request: Request,
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    lang: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Proxy live matches from remote server (board mode)."""
    client = _get_remote_client(request)
    try:
        return await client.get_live_matches(status=status, source=source, lang=lang, limit=limit)
    except Exception as e:
        logger.warning(f"Live proxy failed: {e}")
        raise HTTPException(status_code=502, detail="Remote server unavailable")


@router.get("/live/matches/{match_id}")
async def proxy_live_match(request: Request, match_id: str):
    """Proxy single live match from remote server (board mode)."""
    client = _get_remote_client(request)
    try:
        return await client.get_live_match(match_id)
    except Exception as e:
        logger.warning(f"Live match proxy failed: {e}")
        raise HTTPException(status_code=502, detail="Remote server unavailable")
