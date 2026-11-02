"""Authenticated account replay history. The request identity never selects an owner."""

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from katrain.web.api.v1.endpoints.auth import require_writable_user
from katrain.web.core.baipu_history import (
    BaipuHistoryConflict,
    BaipuHistoryNotFound,
    BaipuHistoryValidationError,
)
from katrain.web.models import User

router = APIRouter()


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpenHistory(StrictBody):
    sgf_content: str = Field(min_length=1, max_length=1048576)
    source_id: str = Field(default="", max_length=128)
    name: str = Field(default="", max_length=512)


class SaveHistory(StrictBody):
    k: int = Field(ge=0, strict=True)
    expected_local_revision: int = Field(ge=0, strict=True)
    mutation_id: str = Field(min_length=1, max_length=128)


class SyncHistory(OpenHistory):
    sgf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_version: int = Field(ge=1, strict=True)
    total: int = Field(ge=1, strict=True)
    k: int = Field(ge=0, strict=True)
    writer_id: str = Field(min_length=1, max_length=128)
    writer_seq: int = Field(ge=0, strict=True)
    expected_revision: int = Field(ge=0, strict=True)


class ResolveHistory(StrictBody):
    strategy: Literal["use_cloud", "keep_local"]
    expected_local_revision: int = Field(ge=0, strict=True)


SUMMARY_FIELDS = (
    "id",
    "source_id",
    "name",
    "sgf_sha256",
    "replay_version",
    "k",
    "total",
    "completed",
    "local_revision",
    "cloud_revision",
    "updated_at",
    "completed_at",
    "sync_state",
)


def public_record(row, *, detail=True, authority="this_node"):
    result = {key: row[key] for key in SUMMARY_FIELDS}
    result["authority"] = row.get("authority", "local_cache" if row["sync_state"] != "synced" else authority)
    if detail:
        result["sgf_content"] = row["sgf_content"]
        conflict = row.get("conflict_remote")
        result["conflict_remote"] = (
            {key: conflict[key] for key in ("k", "total", "updated_at", "cloud_revision")} if conflict else None
        )
    return result


def sync_record(row):
    # Transport needs a complete immutable snapshot and causal receipt, but not
    # this node's private outbox or browser mutation bookkeeping.
    fields = (
        *SUMMARY_FIELDS,
        "sgf_content",
        "writer_id",
        "writer_seq",
        "last_writer_id",
        "last_writer_seq",
        "authority",
    )
    return {key: row[key] for key in fields if key in row}


async def history_owner(
    user: User = Depends(require_writable_user),
    expected: str | None = Header(default=None, alias="X-Katrain-Expected-Identity", max_length=512),
):
    identity = user.uuid or f"{user.id}:{user.username}"
    if expected is not None and expected != identity:
        raise HTTPException(status_code=409, detail={"code": "identity_changed"})
    return user


def service(request):
    instance = getattr(request.app.state, "baipu_history_service", None)
    if instance is None:
        raise HTTPException(status_code=503, detail={"code": "history_unavailable"})
    return instance


async def invoke(awaitable, *, sync=False):
    try:
        return await awaitable
    except BaipuHistoryNotFound as exc:
        raise HTTPException(status_code=404, detail="History not found") from exc
    except BaipuHistoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BaipuHistoryConflict as exc:
        current = exc.current
        if current is not None:
            current = sync_record(current) if sync else public_record(current)
        raise HTTPException(status_code=409, detail={"code": exc.code, "current": current}) from exc
    except RuntimeError as exc:
        # The transport service has one bounded unavailable exception. Do not
        # turn unrelated programming errors into successful empty history.
        if getattr(exc, "code", None) == "history_cloud_unavailable":
            raise HTTPException(status_code=503, detail={"code": exc.code}) from exc
        raise


@router.get("")
async def list_history(
    request: Request, limit: int = Query(default=30, ge=1, le=100), user: User = Depends(history_owner)
):
    result = await invoke(service(request).list(user.id, limit))
    authority = result.get("authority", "cloud")
    return {
        "items": [public_record(row, detail=False, authority=authority) for row in result["items"]],
        "authority": authority,
    }


@router.post("/open")
async def open_history(body: OpenHistory, request: Request, user: User = Depends(history_owner)):
    return public_record(await invoke(service(request).open(user.id, body.model_dump())))


@router.get("/{record_id}")
async def get_history(record_id: str, request: Request, user: User = Depends(history_owner)):
    return public_record(await invoke(service(request).get(user.id, record_id)))


@router.put("/{record_id}")
async def save_history(record_id: str, body: SaveHistory, request: Request, user: User = Depends(history_owner)):
    return public_record(await invoke(service(request).save(user.id, record_id, body.model_dump())))


@router.put("/{record_id}/sync")
async def sync_history(record_id: str, body: SyncHistory, request: Request, user: User = Depends(history_owner)):
    result = await invoke(service(request).accept_sync(user.id, record_id, body.model_dump()), sync=True)
    return sync_record(result)


@router.post("/{record_id}/resolve")
async def resolve_history(record_id: str, body: ResolveHistory, request: Request, user: User = Depends(history_owner)):
    return public_record(
        await invoke(service(request).resolve(user.id, record_id, body.strategy, body.expected_local_revision))
    )
