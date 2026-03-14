import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.core.db import get_db
from katrain.web.core.models_db import User
from katrain.web.tutorials.models import (
    Category,
    Example,
    ProgressUpdate,
    Topic,
    TutorialProgress,
)
from katrain.web.tutorials import progress as progress_repo

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Version directory base path used to validate asset refs stay in-bounds ──
_PARDIR = ".."


def _loader(request: Request):
    loader = getattr(request.app.state, "tutorial_loader", None)
    if loader is None:
        raise HTTPException(status_code=503, detail="Tutorial module not initialized")
    return loader


def _safe_asset_path(loader, asset_path: str) -> Path:
    """Resolve asset path and reject any path traversal attempts."""
    resolved = (loader.get_asset_path(f"assets/{asset_path}")).resolve()
    base = loader.get_asset_path("assets").resolve()
    if not str(resolved).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid asset path")
    return resolved


@router.get("/categories", response_model=List[Category])
async def get_categories(request: Request):
    return _loader(request).get_categories()


@router.get("/categories/{slug}/topics", response_model=List[Topic])
async def get_topics(slug: str, request: Request):
    return _loader(request).get_topics_by_category(slug)


@router.get("/topics/{topic_id}", response_model=Topic)
async def get_topic(topic_id: str, request: Request):
    topic = _loader(request).get_topic(topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.get("/topics/{topic_id}/examples", response_model=List[Example])
async def get_topic_examples(topic_id: str, request: Request):
    loader = _loader(request)
    if loader.get_topic(topic_id) is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return loader.get_examples_for_topic(topic_id)


@router.get("/examples/{example_id}", response_model=Example)
async def get_example(example_id: str, request: Request):
    example = _loader(request).get_example(example_id)
    if example is None:
        raise HTTPException(status_code=404, detail="Example not found")
    return example


@router.get("/assets/{asset_path:path}")
async def get_asset(asset_path: str, request: Request):
    """Serve a published asset. Path traversal outside the assets directory is rejected."""
    file_path = _safe_asset_path(_loader(request), asset_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(file_path)


@router.get("/progress", response_model=List[TutorialProgress])
async def get_progress(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return progress_repo.get_user_progress(db, current_user.id)


@router.post("/progress/{example_id}", response_model=TutorialProgress)
async def update_progress(
    example_id: str,
    update: ProgressUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if _loader(request).get_example(example_id) is None:
        raise HTTPException(status_code=404, detail="Example not found")
    return progress_repo.upsert_progress(
        db, current_user.id, example_id, update.topic_id, update.last_step_id, update.completed
    )
