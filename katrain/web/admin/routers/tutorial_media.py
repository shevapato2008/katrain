"""Authenticated durable media tasks and unsaved replay proposals."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from katrain.web.admin.routers.tutorials import (
    VersionedWrite,
    _audit,
    _cas_update,
    _commit,
    _load,
    _output,
    _version_filter,
    get_admin_db,
)
from katrain.web.admin.session import get_current_admin
from katrain.web.core.models_db import TutorialMediaTask
from katrain.web.tutorials.media_tasks import task_output
from katrain.web.tutorials.manual_review import (
    make_review,
    stored_file_sha256,
    video_artifact,
    video_content_sha256,
    video_problem,
)
from katrain.web.tutorials.models import TutorialFigureAdminOut as TutorialFigureOut
from katrain.web.tutorials.replay import replay_draft, replay_draft_warnings

router = APIRouter(dependencies=[Depends(get_current_admin)])


class MediaTaskWrite(VersionedWrite):
    kind: Literal["audio", "video"]
    render_mode: Literal["2d", "3d"] = "2d"


@router.post("/figures/{figure_id}/media-tasks", status_code=202)
def create_media_task(
    figure_id: int,
    body: MediaTaskWrite,
    request: Request,
    db: Session = Depends(get_admin_db),
    admin: dict = Depends(get_current_admin),
):
    task = request.app.state.media_worker.enqueue(db, _load(db, figure_id), body, admin)
    return {"task": task_output(task)}


@router.get("/media-tasks/{task_id}")
def get_media_task(task_id: str, db: Session = Depends(get_admin_db)):
    task = db.get(TutorialMediaTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Media task not found")
    return {"task": task_output(task)}


@router.get("/figures/{figure_id}/media-tasks")
def get_figure_media_tasks(figure_id: int, db: Session = Depends(get_admin_db)):
    _load(db, figure_id)
    tasks = db.scalars(
        select(TutorialMediaTask)
        .where(TutorialMediaTask.figure_id == figure_id)
        .order_by(TutorialMediaTask.created_at, TutorialMediaTask.id)
    ).all()
    return {"tasks": [task_output(task) for task in tasks]}


@router.post("/figures/{figure_id}/replay-draft")
def propose_replay_draft(figure_id: int, body: VersionedWrite, db: Session = Depends(get_admin_db)):
    figure = _load(db, figure_id)
    _version_filter(db, figure, body.expected_updated_at)
    if not figure.board_payload:
        raise HTTPException(status_code=422, detail="Save a board before proposing a replay draft")
    return {
        "board_payload": replay_draft(figure.board_payload),
        "saved": False,
        "warnings": replay_draft_warnings(figure.board_payload),
    }


class VideoApprovalWrite(VersionedWrite):
    render_mode: Literal["2d", "3d"]
    expected_asset: str = Field(min_length=1, max_length=512)


@router.put("/figures/{figure_id}/approve-video", response_model=TutorialFigureOut)
def approve_video(
    figure_id: int,
    body: VideoApprovalWrite,
    request: Request,
    db: Session = Depends(get_admin_db),
    admin: dict = Depends(get_current_admin),
):
    figure = _load(db, figure_id)
    _version_filter(db, figure, body.expected_updated_at)
    artifact = video_artifact(figure, body.render_mode)
    if not artifact or artifact.get("asset") != body.expected_asset:
        raise HTTPException(status_code=409, detail="Video asset changed. Reload and review the current video.")
    problem = video_problem(figure, body.render_mode)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    try:
        checksum = stored_file_sha256(request.app.state.media_worker.storage, body.expected_asset)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Video storage unavailable; retry manual approval later") from exc
    if checksum != artifact["sha256"]:
        raise HTTPException(
            status_code=409,
            detail="Video bytes do not match the generated artifact digest. Regenerate before approval.",
        )
    record = make_review(
        admin, video_content_sha256(figure, body.render_mode), asset=body.expected_asset, file_sha256=checksum
    )
    figure = _cas_update(db, figure, body.expected_updated_at, {f"video_{body.render_mode}_review": record})
    _audit(db, admin, f"tutorial.approve_video_{body.render_mode}", figure_id)
    _commit(db)
    return _output(figure)
