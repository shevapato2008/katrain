"""Golden images: list manifests, mark candidate / released / revoked (audited), signed download links."""

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from katrain.web.admin import artifacts
from katrain.web.admin.cron_health import as_utc
from katrain.web.admin.routers.tutorials import get_admin_db
from katrain.web.admin.session import get_current_admin
from katrain.web.core.models_db import AdminAuditLog, GoldenImageStatus

router = APIRouter(dependencies=[Depends(get_current_admin)])
STATUSES = ("candidate", "released", "revoked")


def _config(request: Request):
    return getattr(request.app.state, "artifact_config", None)


def _s3(request: Request, public: bool = False):
    return artifacts.client(_config(request), public=public)


@router.get("/artifacts")
def list_artifacts(request: Request, db: Session = Depends(get_admin_db)):
    config = _config(request)
    if config is None:
        return {"state": "unconfigured", "bucket": None, "images": [], "truncated": False, "error": None}
    try:
        listing = artifacts.list_images(config, _s3(request))
    except Exception as exc:
        return {"state": "unreachable", "bucket": config.bucket, "images": [], "truncated": False, "error": type(exc).__name__}
    statuses = {row.prefix: row for row in db.scalars(select(GoldenImageStatus)).all()}
    for image in listing["images"]:
        row = statuses.get(image["prefix"])
        image["status"] = row.status if row else "candidate"
        image["status_note"] = row.note if row else None
        image["status_by"] = row.changed_by if row else None
        image["status_at"] = as_utc(row.changed_at).isoformat() if row else None
    return {"state": "configured", "bucket": config.bucket, "error": None, **listing}


class StatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prefix: str = Field(max_length=255)
    status: str = Field(pattern="^(candidate|released|revoked)$")
    note: str = Field(max_length=200)

    @field_validator("note")
    @classmethod
    def meaningful(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("note needs at least 5 characters")
        return value


def _known(request: Request, prefix: str) -> dict:
    config = _config(request)
    if config is None:
        raise HTTPException(status_code=409, detail="制品库尚未配置")
    for image in artifacts.list_images(config, _s3(request))["images"]:
        if image["prefix"] == prefix:
            return image
    raise HTTPException(status_code=404, detail="没有这个镜像")


def _audit(db, admin, action, prefix, detail):
    db.add(AdminAuditLog(actor_realm="admin", actor_username=admin["username"], action=action, target_type="golden_image", target_id=None, success=True, detail=json.dumps({"prefix": prefix, **detail}, ensure_ascii=False)))


@router.post("/artifacts/status")
def set_status(body: StatusRequest, request: Request, admin: dict = Depends(get_current_admin), db: Session = Depends(get_admin_db)):
    image = _known(request, body.prefix)
    if body.status == "released" and image["problems"]:
        raise HTTPException(status_code=409, detail="manifest 有问题的镜像不能发布：" + "；".join(image["problems"]))
    row = db.get(GoldenImageStatus, body.prefix)
    previous = row.status if row else "candidate"
    if previous == body.status:
        raise HTTPException(status_code=409, detail="状态没有变化")
    now = datetime.now(timezone.utc)
    if row is None:
        row = GoldenImageStatus(prefix=body.prefix, status=body.status, changed_at=now, changed_by=admin["username"])
        db.add(row)
    row.status, row.note, row.changed_at, row.changed_by = body.status, body.note, now, admin["username"]
    _audit(db, admin, "artifact_status", body.prefix, {"from": previous, "to": body.status, "note": body.note})
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"prefix": body.prefix, "status": body.status}


class LinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prefix: str = Field(max_length=255)


@router.post("/artifacts/link")
def download_link(body: LinkRequest, request: Request, admin: dict = Depends(get_current_admin), db: Session = Depends(get_admin_db)):
    image = _known(request, body.prefix)
    row = db.get(GoldenImageStatus, body.prefix)
    if row is not None and row.status == "revoked":
        raise HTTPException(status_code=409, detail="已撤回的镜像不再提供下载")
    if image["problems"]:
        raise HTTPException(status_code=409, detail="manifest 有问题，不提供下载：" + "；".join(image["problems"]))
    url = artifacts.signed_link(_config(request), body.prefix + image["manifest"]["file"], _s3(request, public=True))
    expires = datetime.now(timezone.utc) + timedelta(seconds=artifacts.LINK_TTL_S)
    _audit(db, admin, "artifact_link", body.prefix, {"expires_at": expires.isoformat()})
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"url": url, "expires_at": expires.isoformat(), "sha256": image["manifest"]["sha256"]}
