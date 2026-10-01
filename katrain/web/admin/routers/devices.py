"""Box fleet view: online / offline / never-reported / pending / rejected, and approve or reject."""

import json
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from katrain.web.admin.cron_health import as_utc
from katrain.web.admin.routers.tutorials import get_admin_db
from katrain.web.admin.session import get_current_admin
from katrain.web.core import device_telemetry as dt
from katrain.web.core.models_db import AdminAuditLog, BoxDevice

router = APIRouter(dependencies=[Depends(get_current_admin)])


def _iso(value):
    return as_utc(value).isoformat() if value is not None else None


def _state(device: BoxDevice, now: datetime) -> str:
    if device.status != "approved":
        return device.status  # pending | rejected
    if device.last_seen is None:
        return "never"
    return "online" if (now - as_utc(device.last_seen)).total_seconds() <= dt.ONLINE_WITHIN_S else "offline"


@router.get("/devices")
def list_devices(db: Session = Depends(get_admin_db)):
    now = datetime.now(timezone.utc)
    devices = db.scalars(select(BoxDevice).order_by(BoxDevice.device_id)).all()
    rows = []
    for d in devices:
        rows.append(
            {
                "device_id": d.device_id, "state": _state(d, now), "status": d.status,
                "registered_at": _iso(d.registered_at), "decided_at": _iso(d.decided_at), "decided_by": d.decided_by,
                "last_seen": _iso(d.last_seen), "silent_s": round((now - as_utc(d.last_seen)).total_seconds()) if d.last_seen else None,
                "last_ip": d.last_ip, "board": d.board, "smartbox_version": d.smartbox_version,
                "katrain_build": d.katrain_build, "mode": d.mode, "uptime_s": d.uptime_s,
            }
        )
    approved = [r for r in rows if r["status"] == "approved"]
    return {
        "observed_at": now.isoformat(),
        "online_within_s": dt.ONLINE_WITHIN_S,
        "devices": rows,
        "counts": dict(Counter(r["state"] for r in rows)),
        "versions": {
            "smartbox": dict(Counter(r["smartbox_version"] or "未上报" for r in approved if r["last_seen"])),
            "katrain": dict(Counter(r["katrain_build"] or "未上报" for r in approved if r["last_seen"])),
        },
    }


def _decide(device_id: str, decision: str, admin: dict, db: Session):
    device = db.get(BoxDevice, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.status != "pending":
        raise HTTPException(status_code=409, detail="只能批准或拒绝待批准的设备")
    now = datetime.now(timezone.utc)
    device.status, device.decided_at, device.decided_by = decision, now, admin["username"]
    db.add(
        AdminAuditLog(
            actor_realm="admin", actor_username=admin["username"], action={"approved": "device_approve", "rejected": "device_reject"}[decision],
            target_type="box_device", target_id=None, success=True,
            detail=json.dumps({"device_id": device_id, "board": device.board, "ip": device.last_ip}, ensure_ascii=False),
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"device_id": device_id, "status": decision}


@router.post("/devices/{device_id}/approve")
def approve(device_id: str, admin: dict = Depends(get_current_admin), db: Session = Depends(get_admin_db)):
    return _decide(device_id, "approved", admin, db)


@router.post("/devices/{device_id}/reject")
def reject(device_id: str, admin: dict = Depends(get_current_admin), db: Session = Depends(get_admin_db)):
    return _decide(device_id, "rejected", admin, db)


@router.post("/devices/{device_id}/reset")
def reset(device_id: str, admin: dict = Depends(get_current_admin), db: Session = Depends(get_admin_db)):
    """Forget a registration (e.g. a squatted id or a mistaken rejection) so the real box can register again."""
    device = db.get(BoxDevice, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    db.add(
        AdminAuditLog(
            actor_realm="admin", actor_username=admin["username"], action="device_reset", target_type="box_device",
            target_id=None, success=True,
            detail=json.dumps({"device_id": device_id, "previous_status": device.status, "ip": device.last_ip}, ensure_ascii=False),
        )
    )
    db.delete(device)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"device_id": device_id, "status": "reset"}
