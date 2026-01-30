"""REST API endpoints for the kifu album (tournament game records) module."""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
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
def list_kifu_albums(
    q: Optional[str] = Query(None, description="Search query (fuzzy match on player names, event, date)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List tournament game records with optional search and pagination."""
    query = db.query(KifuAlbum).options(defer(KifuAlbum.sgf_content), defer(KifuAlbum.search_text))

    if q:
        # search_text is stored lowercased; match with lower(q)
        query = query.filter(KifuAlbum.search_text.contains(q.lower()))

    # Sort by normalized date descending, then by id for deterministic pagination
    query = query.order_by(KifuAlbum.date_sort.desc(), KifuAlbum.id.desc())

    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    return KifuAlbumListResponse(
        items=[KifuAlbumSummary.model_validate(r) for r in records],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/albums/{album_id}", response_model=KifuAlbumDetail)
def get_kifu_album(album_id: int, db: Session = Depends(get_db)):
    """Get a single kifu album record with full SGF content."""
    record = db.query(KifuAlbum).filter(KifuAlbum.id == album_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Kifu album {album_id} not found")

    return KifuAlbumDetail.model_validate(record)
