"""Audited control plane for the central PvP lobby bot population.

The admin ASGI process has no in-memory lobby. It reads the central process's
timestamped database snapshot and never invents live counts from configuration.
"""

import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from katrain.web.admin.routers.tutorials import get_admin_db
from katrain.web.admin.session import get_current_admin
from katrain.core import ladder
from katrain.web.core.models_db import AdminAuditLog, AiLadderProfile, SystemConfigDB, User
from katrain.web.core.pvp_lobby_bots import playable_rungs, validate_config

router = APIRouter(dependencies=[Depends(get_current_admin)])
CONFIG_KEY = "pvp_lobby_bot_config"
RUNTIME_KEY = "pvp_lobby_bot_runtime"
RUNTIME_STALE_AFTER_S = 30


class LobbyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    enabled: StrictBool
    bot_game_limit: StrictInt = Field(ge=0, le=6)
    idle_targets: dict[str, StrictInt]


class ConfigWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: StrictInt = Field(ge=0)
    config: LobbyConfig


def _default_config() -> dict:
    return validate_config({"version": 1, "enabled": False, "bot_game_limit": 3, "idle_targets": {}})


def _saved_config(db: Session) -> tuple[int, dict, str | None]:
    row = db.get(SystemConfigDB, CONFIG_KEY)
    if row is None or not row.value:
        return 0, _default_config(), None
    try:
        saved = json.loads(row.value)
        return int(saved["revision"]), validate_config(saved["config"]), row.value
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "大厅配置损坏，请联系运维。") from exc


def _snapshot(db: Session) -> dict | None:
    row = db.get(SystemConfigDB, RUNTIME_KEY)
    if row is None or not row.value:
        return None
    try:
        value = json.loads(row.value)
        if not isinstance(value, dict):
            return None
        return value
    except (ValueError, TypeError):
        return None


def _reported_at(reported: dict | None) -> datetime | None:
    if reported and isinstance(reported.get("reported_at"), str):
        try:
            timestamp = datetime.fromisoformat(reported["reported_at"].replace("Z", "+00:00"))
            return timestamp if timestamp.tzinfo is not None else None
        except ValueError:
            pass
    return None


def _snapshot_fresh(reported: dict | None) -> bool:
    timestamp = _reported_at(reported)
    return timestamp is not None and 0 <= (datetime.now(timezone.utc) - timestamp).total_seconds() <= RUNTIME_STALE_AFTER_S


def _runtime(db: Session, config: dict) -> dict:
    reported = _snapshot(db)
    timestamp = _reported_at(reported)
    stale = not _snapshot_fresh(reported)
    counts = {r.get("rung"): r for r in reported.get("rungs", []) if isinstance(r, dict)} if reported else {}
    ranks = [
        {
            "rung": level.rung,
            "rank_label": level.rank_label,
            "idle_target": config["idle_targets"][str(level.rung)],
            "idle_now": counts.get(level.rung, {}).get("idle_now") if reported else None,
            "playing_now": counts.get(level.rung, {}).get("playing_now") if reported else None,
        }
        for level in playable_rungs()
    ]
    return {
        "reported_at": reported.get("reported_at") if timestamp else None,
        "applied_config_revision": reported.get("applied_config_revision") if reported else None,
        "stale": stale,
        "active_bot_games": reported.get("active_bot_games") if reported else None,
        "engine_errors": reported.get("engine_errors") if reported else None,
        "rungs": ranks,
    }


@router.get("/pvp-lobby")
def get_lobby(db: Session = Depends(get_admin_db)):
    revision, config, _ = _saved_config(db)
    return {"config": config, "config_revision": revision, "runtime": _runtime(db, config)}


@router.put("/pvp-lobby/config")
def put_config(body: ConfigWrite, admin: dict = Depends(get_current_admin), db: Session = Depends(get_admin_db)):
    try:
        normalized = validate_config(body.config.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    revision, old_config, old_value = _saved_config(db)
    if body.expected_revision != revision:
        raise HTTPException(409, "大厅设置已被其他管理员修改，请重新读取。")
    next_revision = revision + 1
    value = json.dumps({"revision": next_revision, "config": normalized}, ensure_ascii=False, sort_keys=True)
    try:
        if old_value is None:
            db.add(SystemConfigDB(key=CONFIG_KEY, value=value, description="Central PvP lobby bot settings"))
            db.flush()
        else:
            changed = db.execute(
                update(SystemConfigDB).where(SystemConfigDB.key == CONFIG_KEY, SystemConfigDB.value == old_value).values(value=value)
            ).rowcount
            if changed != 1:
                db.rollback()
                raise HTTPException(409, "大厅设置已被其他管理员修改，请重新读取。")
        db.add(AdminAuditLog(
            actor_realm="admin", actor_username=admin["username"], action="pvp_lobby_config_update",
            target_type="pvp_lobby", target_id=None, success=True,
            detail=json.dumps({"old_revision": revision, "new_revision": next_revision, "before": old_config, "after": normalized}, ensure_ascii=False),
        ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "大厅设置已被其他管理员修改，请重新读取。") from exc
    except Exception:
        db.rollback()
        raise
    return {"config": normalized, "config_revision": next_revision, "runtime": _runtime(db, normalized)}


@router.get("/pvp-lobby/participants")
def get_participants(
    page: int = Query(1, ge=1), page_size: int = Query(30, ge=1),
    kind: Literal["all", "human", "bot"] = "all",
    presence: Literal["all", "online", "idle", "playing", "offline"] = "all",
    q: str = Query("", max_length=100), db: Session = Depends(get_admin_db),
):
    size = min(page_size, 100)
    offset = (page - 1) * size
    rows = _snapshot(db)
    fresh = _snapshot_fresh(rows)
    present = {p.get("id"): p for p in rows.get("participants", []) if isinstance(p, dict)} if rows else {}
    human_ids = {id for id, row in present.items() if row.get("kind") == "human" and type(id) is int and id > 0} if fresh else set()
    bot_rows = [row for row in present.values() if row.get("kind") == "bot" and type(row.get("id")) is int and row["id"] < 0]
    if not fresh:
        bot_rows = [{**row, "presence": "unknown"} for row in bot_rows]
    if q:
        bot_rows = [row for row in bot_rows if q.casefold() in str(row.get("username", "")).casefold()]
    if presence != "all":
        bot_rows = [row for row in bot_rows if row.get("presence") in ({"idle", "playing"} if presence == "online" else {presence})]
    bot_rows.sort(key=lambda row: row["id"], reverse=True)
    query = select(User.id, User.username, AiLadderProfile.ai_ladder_rung).outerjoin(AiLadderProfile, AiLadderProfile.user_id == User.id)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(User.username.ilike(f"%{escaped}%", escape="\\"))
    if presence in {"idle", "playing", "online"}:
        ids = {id for id in human_ids if presence == "online" or present[id].get("presence") == presence}
        query = query.where(User.id.in_(ids))
    elif presence == "offline":
        query = query.where(~User.id.in_(human_ids) if fresh else User.id.in_([]))
    human_total = db.scalar(select(func.count()).select_from(query.subquery())) if kind != "bot" else 0
    bot_total = len(bot_rows) if kind != "human" else 0
    results = []
    rank_names = {level.rung: level.rank_name for level in ladder.LADDER_LEVELS}
    if kind != "bot" and offset < human_total:
        for user_id, username, rung in db.execute(query.order_by(User.id).offset(offset).limit(size)):
            row = present.get(user_id, {})
            results.append({"id": user_id, "username": username, "kind": "human", "ladder_rung": rung,
                            "rank_label": rank_names.get(rung), "presence": row.get("presence", "offline") if fresh else "unknown"})
    bot_start = offset if kind == "bot" else max(0, offset - human_total)
    for row in bot_rows[bot_start:bot_start + size - len(results)]:
        results.append({"id": row["id"], "username": row.get("username", ""), "kind": "bot",
                        "ladder_rung": row.get("ladder_rung"), "rank_label": row.get("rank_label"),
                        "presence": row.get("presence", "offline")})
    return {"items": results, "total": human_total + bot_total, "page": page, "page_size": size}
