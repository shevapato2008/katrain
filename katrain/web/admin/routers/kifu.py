"""Admin-only read of the environment's kifu library, used to pick a game for capture."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, defer

from katrain.web.admin.routers.tutorials import get_admin_db
from katrain.web.admin.session import get_current_admin
from katrain.web.api.v1.endpoints.kifu import KifuAlbumDetail, KifuAlbumListResponse, KifuAlbumSummary
from katrain.web.core.models_db import KifuAlbum

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("/albums", response_model=KifuAlbumListResponse)
def search_albums(
    q: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_admin_db),
):
    # Capture only accepts 19×19 records, so smaller boards are never offered.
    condition = KifuAlbum.board_size == 19
    if q and q.strip():
        condition = condition & KifuAlbum.search_text.contains(q.strip().lower())
    total = db.query(func.count(KifuAlbum.id)).filter(condition).scalar() or 0
    records = (
        db.query(KifuAlbum)
        .options(defer(KifuAlbum.sgf_content), defer(KifuAlbum.search_text))
        .filter(condition)
        .order_by(KifuAlbum.date_sort.desc().nulls_last(), KifuAlbum.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return KifuAlbumListResponse(
        items=[KifuAlbumSummary.model_validate(record) for record in records],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/albums/{album_id}", response_model=KifuAlbumDetail)
def album_detail(album_id: int, db: Session = Depends(get_admin_db)):
    record = db.query(KifuAlbum).filter(KifuAlbum.id == album_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Kifu album not found")
    return KifuAlbumDetail.model_validate(record)
