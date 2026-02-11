"""REST API endpoints for the kifu album (tournament game records) module."""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, defer

from katrain.web.core.db import get_db
from katrain.web.core.models_db import KifuAlbum

router = APIRouter()


class KifuAlbumSummary(BaseModel):
    """Summary response for kifu album listing (excludes sgf_content)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    player_black: str
    player_white: str
    black_rank: Optional[str]
    white_rank: Optional[str]
    event: Optional[str]
    result: Optional[str]
    rules: Optional[str]
    date_played: Optional[str]
    komi: Optional[float]
    handicap: int
    board_size: int
    round_name: Optional[str]
    move_count: int


class KifuAlbumDetail(KifuAlbumSummary):
    """Full response including SGF content."""
    place: Optional[str]
    rules: Optional[str]
    source: Optional[str]
    sgf_content: str


class KifuAlbumListResponse(BaseModel):
    """Paginated list response."""
    items: List[KifuAlbumSummary]
    total: int
    page: int
    page_size: int


@router.get("/albums", response_model=KifuAlbumListResponse)
async def list_kifu_albums(
    request: Request,
    q: Optional[str] = Query(None, description="Search query (fuzzy match on player names, event, date)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List tournament game records with optional search and pagination."""
    # Board mode: delegate to repository dispatcher
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        return await dispatcher.kifu_list_albums(q, page, page_size)

    query = db.query(KifuAlbum).options(defer(KifuAlbum.sgf_content), defer(KifuAlbum.search_text))

    if q:
        # search_text is stored lowercased; match with lower(q)
        query = query.filter(KifuAlbum.search_text.contains(q.lower()))

    # Sort by normalized date descending (nulls last), then by id for deterministic pagination
    query = query.order_by(KifuAlbum.date_sort.desc().nulls_last(), KifuAlbum.id.desc())

    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    return KifuAlbumListResponse(
        items=[KifuAlbumSummary.model_validate(r) for r in records],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/albums/{album_id}", response_model=KifuAlbumDetail)
async def get_kifu_album(request: Request, album_id: int, db: Session = Depends(get_db)):
    """Get a single kifu album record with full SGF content."""
    # Board mode: delegate to repository dispatcher
    dispatcher = getattr(request.app.state, "repository_dispatcher", None)
    if dispatcher is not None:
        result = await dispatcher.kifu_get_album(album_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Kifu album {album_id} not found")
        return result

    record = db.query(KifuAlbum).filter(KifuAlbum.id == album_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Kifu album {album_id} not found")

    return KifuAlbumDetail.model_validate(record)
