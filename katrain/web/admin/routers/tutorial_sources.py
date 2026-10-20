"""Protected, read-only access to the catalog's original page assets and text."""

from pathlib import PurePosixPath
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from katrain.web.admin.routers.tutorials import get_admin_db
from katrain.web.admin.session import get_current_admin
from katrain.web.core.models_db import TutorialBook
from katrain.web.tutorials.source_models import TutorialSourceBook, TutorialSourceFigure, TutorialSourcePage

router = APIRouter(dependencies=[Depends(get_current_admin)])


class SourcePageSummary(BaseModel):
    page: int
    page_image_path: str
    has_text: bool
    figure_count: int


class SourcePageList(BaseModel):
    book_id: int
    source_catalog_id: str
    pages: list[SourcePageSummary]


class SourceTextFragment(BaseModel):
    kind: Literal["description", "figure_ref"]
    text: str
    source_figure_id: str | None = None
    chapter_title: str
    section_title: str
    source_pointer: str


class SourceBBox(BaseModel):
    x_min: float = Field(ge=0, le=1)
    y_min: float = Field(ge=0, le=1)
    x_max: float = Field(ge=0, le=1)
    y_max: float = Field(ge=0, le=1)


class SourceFigureReference(BaseModel):
    source_figure_id: str
    figure_id: int | None
    figure_label: str
    bbox: SourceBBox
    match_reason: str | None


class SourcePageDetail(BaseModel):
    book_id: int
    page: int
    page_image_path: str
    page_context_text: str
    text_fragments: list[SourceTextFragment]
    figures: list[SourceFigureReference]


def _unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="Tutorial source pages are unavailable")


def _asset_path(value: str) -> str:
    """Expose only a storage key, never a local path or arbitrary remote URL."""
    path = PurePosixPath(value)
    if not value.startswith("tutorial_assets/") or "\\" in value or ".." in path.parts or ":" in value:
        raise _unavailable()
    return value


def _load_source(db: Session, book_id: int) -> TutorialSourceBook | None:
    if db.get(TutorialBook, book_id) is None:
        raise HTTPException(status_code=404, detail="Book not found")
    sources = db.scalars(
        select(TutorialSourceBook)
        .where(TutorialSourceBook.book_id == book_id, TutorialSourceBook.source_namespace == "curriculum")
        .limit(2)
    ).all()
    if len(sources) > 1:
        raise _unavailable()
    return sources[0] if sources else None


@router.get("/books/{book_id}/source-pages", response_model=SourcePageList)
def list_source_pages(book_id: int, db: Session = Depends(get_admin_db)):
    try:
        source = _load_source(db, book_id)
        if source is None:
            return SourcePageList(book_id=book_id, source_catalog_id="", pages=[])
        counts = (
            select(TutorialSourceFigure.page, func.count(TutorialSourceFigure.id).label("figure_count"))
            .where(TutorialSourceFigure.source_book_id == source.id)
            .group_by(TutorialSourceFigure.page)
            .subquery()
        )
        rows = db.execute(
            select(
                TutorialSourcePage.page,
                TutorialSourcePage.page_image_path,
                (func.length(func.trim(TutorialSourcePage.page_context_text)) > 0).label("has_context_text"),
                func.coalesce(counts.c.figure_count, 0).label("figure_count"),
            )
            .outerjoin(counts, counts.c.page == TutorialSourcePage.page)
            .where(TutorialSourcePage.source_book_id == source.id)
            .order_by(TutorialSourcePage.page)
        ).all()
        return SourcePageList(
            book_id=book_id,
            source_catalog_id=source.catalog_id,
            pages=[
                SourcePageSummary(
                    page=row.page,
                    page_image_path=_asset_path(row.page_image_path),
                    has_text=bool(row.has_context_text or row.figure_count),
                    figure_count=row.figure_count,
                )
                for row in rows
            ],
        )
    except (OperationalError, ProgrammingError, ValidationError) as exc:
        raise _unavailable() from exc


@router.get("/books/{book_id}/source-pages/{page}", response_model=SourcePageDetail)
def get_source_page(book_id: int, page: int, db: Session = Depends(get_admin_db)):
    try:
        source = _load_source(db, book_id)
        original = (
            db.scalar(
                select(TutorialSourcePage).where(
                    TutorialSourcePage.source_book_id == source.id, TutorialSourcePage.page == page
                )
            )
            if source is not None
            else None
        )
        if original is None:
            raise HTTPException(status_code=404, detail="Source page not found")
        references = db.scalars(
            select(TutorialSourceFigure)
            .where(TutorialSourceFigure.source_book_id == source.id, TutorialSourceFigure.page == page)
            .order_by(TutorialSourceFigure.id)
        ).all()
        return SourcePageDetail(
            book_id=book_id,
            page=page,
            page_image_path=_asset_path(original.page_image_path),
            page_context_text=original.page_context_text,
            text_fragments=[
                SourceTextFragment(
                    kind=fragment.get("kind"),
                    text=fragment.get("text", ""),
                    source_figure_id=fragment.get("source_figure_id"),
                    chapter_title=fragment.get("chapter_title", ""),
                    section_title=fragment.get("section_title", ""),
                    source_pointer=fragment.get("pointer", ""),
                )
                for fragment in original.text_fragments
            ],
            figures=[
                SourceFigureReference(
                    source_figure_id=reference.source_figure_id,
                    figure_id=reference.figure_id,
                    figure_label=reference.source_metadata.get("original_caption", {}).get("label", ""),
                    bbox=reference.source_metadata.get("bbox", {}),
                    match_reason=reference.match_reason,
                )
                for reference in references
            ],
        )
    except (OperationalError, ProgrammingError, ValidationError) as exc:
        raise _unavailable() from exc
