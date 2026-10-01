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
    listed = {image["prefix"] for image in listing["images"]}
    if not listing["truncated"]:
        # A status row whose image is gone from the bucket is shown, not silently dropped.
        for prefix, row in statuses.items():
            if prefix not in listed and row.status != "candidate":
                listing["images"].append({"prefix": prefix, "manifest": None, "problems": ["桶里已经没有这个镜像"], "object_size": None, "etag": None})
    for image in listing["images"]:
        row = statuses.get(image["prefix"])
        _check_binding(image, row)
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


def _check_binding(image: dict, row) -> None:
    if row is not None and row.status == "released" and row.released_etag and image.get("etag") is not None:
        if image["etag"] != row.released_etag or image["object_size"] != row.released_size:
            image["problems"].append("发布后文件被改动过（与发布时的字节不一致）")


def _known(request: Request, prefix: str, db: Session) -> dict:
    config = _config(request)
    if config is None:
        raise HTTPException(status_code=409, detail="制品库尚未配置")
    if not artifacts.PREFIX.match(prefix):
        raise HTTPException(status_code=404, detail="没有这个镜像")
    image = artifacts.read_image(config, _s3(request), prefix)
    if image["manifest"] is None and image["problems"] == ["没有 manifest"]:
        raise HTTPException(status_code=404, detail="没有这个镜像")
    _check_binding(image, db.get(GoldenImageStatus, prefix))
    return image


def _audit(db, admin, action, prefix, detail):
    db.add(AdminAuditLog(actor_realm="admin", actor_username=admin["username"], action=action, target_type="golden_image", target_id=None, success=True, detail=json.dumps({"prefix": prefix, **detail}, ensure_ascii=False)))


@router.post("/artifacts/status")
def set_status(body: StatusRequest, request: Request, admin: dict = Depends(get_current_admin), db: Session = Depends(get_admin_db)):
    image = _known(request, body.prefix, db)
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
    if body.status == "released":
        row.released_etag, row.released_size = image["etag"], image["object_size"]
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
    image = _known(request, body.prefix, db)
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
